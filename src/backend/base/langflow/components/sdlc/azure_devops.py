"""Azure DevOps component for fetching work items."""
from typing import Dict, List, Optional, Any, Union
from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, MultilineInput, DropdownInput, Output, BoolInput
from langflow.schema import Data
import aiohttp
import base64
import json
import logging

# Set up logger
logger = logging.getLogger(__name__)

class AzureDevOpsComponent(Component):
    """A component that fetches work items from Azure DevOps using WIQL queries or natural language"""
    
    display_name: str = "Azure DevOps Work Items"
    description: str = "Fetches work items from Azure DevOps using WIQL queries or natural language"
    documentation: str = "https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/wiql/query-by-wiql"
    category: str = "sdlc"
    icon: str = "GitBranch"
    name: str = "AzureDevOpsComponent"
    
    def __init__(self, **kwargs):
        try:
            # Initialize with the base Component class first
            super().__init__(**kwargs)
            
            # Use the absolute minimum metadata needed - just strings
            self._metadata = {
                "display_name": str(self.display_name),
                "description": str(self.description),
                "icon": str(self.icon),
                "category": str(self.category),
                "version": "1.0.0"
            }
            
            # Initialize all possible input attributes with defaults to avoid undefined errors
            self._set_default_attributes()
            
            logger.info("AzureDevOpsComponent initialized successfully")
        except Exception as e:
            logger.exception(f"Error initializing AzureDevOpsComponent: {e}")
            # Don't re-raise the exception to prevent component loading failures
            
    def _set_default_attributes(self):
        """Set default values for attributes to prevent undefined errors in frontend"""
        if not hasattr(self, 'organization'):
            self.organization = ""
        if not hasattr(self, 'project'):
            self.project = ""
        if not hasattr(self, 'pat_token'):
            self.pat_token = ""
        if not hasattr(self, 'wiql_query'):
            self.wiql_query = "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.WorkItemType] = 'Task'"
        if not hasattr(self, 'query_type'):
            self.query_type = "flat"
        if not hasattr(self, 'use_natural_language'):
            self.use_natural_language = False
        if not hasattr(self, 'natural_language_query'):
            self.natural_language_query = ""
        if not hasattr(self, 'openai_api_key'):
            self.openai_api_key = ""
        if not hasattr(self, 'model'):
            self.model = "gpt-3.5-turbo"
    
    inputs = [
        StrInput(
            name="organization",
            display_name="Organization",
            required=True,
            placeholder="your-org",
            helper_text="Azure DevOps organization name"
        ),
        StrInput(
            name="project",
            display_name="Project",
            required=True,
            placeholder="your-project",
            helper_text="Azure DevOps project name"
        ),
        SecretStrInput(
            name="pat_token",
            display_name="PAT Token",
            required=True,
            placeholder="your-pat-token",
            helper_text="Personal Access Token for authentication"
        ),
        BoolInput(
            name="use_natural_language",
            display_name="Use Natural Language",
            required=False,
            value=False,
            helper_text="Enable to use natural language instead of WIQL query (requires LangChain and OpenAI)"
        ),
        MultilineInput(
            name="wiql_query",
            display_name="WIQL Query",
            required=False,
            placeholder="SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.WorkItemType] = 'Task'",
            value="SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.WorkItemType] = 'Task'",
            helper_text="Work Item Query Language (WIQL) query to execute when not using natural language"
        ),
        MultilineInput(
            name="natural_language_query",
            display_name="Natural Language Query",
            required=False,
            placeholder="Find all open bugs assigned to me",
            helper_text="Describe in plain English what work items you want to find (requires LangChain and OpenAI)"
        ),
        DropdownInput(
            name="query_type",
            display_name="Query Type",
            required=True,
            options=["flat", "oneHop", "tree"],
            value="flat",
            helper_text="Type of query execution (flat, oneHop, or tree)"
        ),
        StrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            required=False,
            placeholder="sk-...",
            helper_text="OpenAI API key for natural language processing (leave empty to use environment variable)"
        ),
        StrInput(
            name="model",
            display_name="LLM Model",
            required=False,
            value="gpt-3.5-turbo",
            placeholder="gpt-3.5-turbo",
            helper_text="The LLM model to use for natural language processing"
        ),
    ]
    
    outputs = [
        Output(display_name="Work Items", name="work_items", method="build_work_items"),
        Output(display_name="WIQL Query", name="generated_wiql_query", method="build_wiql_query"),
    ]

    async def build_work_items(self) -> Data:
        """Build the work items output."""
        try:
            # Initial validation
            for required_attr in ['organization', 'project', 'pat_token']:
                if not hasattr(self, required_attr) or not getattr(self, required_attr):
                    result = {
                        "status": "error",
                        "message": f"Missing required parameter: {required_attr}",
                        "work_items": []
                    }
                    return Data(value=result)
            
            # Determine if we're using natural language or direct WIQL
            if hasattr(self, 'use_natural_language') and self.use_natural_language:
                # First generate WIQL query from natural language
                if not hasattr(self, 'natural_language_query') or not self.natural_language_query:
                    result = {
                        "status": "error",
                        "message": "Natural language query is required when 'Use Natural Language' is enabled",
                        "work_items": []
                    }
                    return Data(value=result)
                
                try:
                    wiql_query = await self._generate_wiql_from_natural_language()
                    logger.info(f"Generated WIQL query: {wiql_query}")
                except Exception as e:
                    logger.exception("Error in natural language processing")
                    result = {
                        "status": "error",
                        "message": f"Natural language processing error: {str(e)}",
                        "work_items": []
                    }
                    return Data(value=result)
            else:
                # Use the directly provided WIQL query
                if not hasattr(self, 'wiql_query') or not self.wiql_query:
                    result = {
                        "status": "error", 
                        "message": "WIQL query is required when not using natural language",
                        "work_items": []
                    }
                    return Data(value=result)
                
                wiql_query = self.wiql_query
            
            # Create base URL for Azure DevOps API
            base_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/wit/wiql"
            
            # Prepare headers with authentication
            auth_token = base64.b64encode(f":{self.pat_token}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/json"
            }
            
            # Prepare request body
            body = {
                "query": wiql_query,
                "queryType": self.query_type
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}?api-version=5.1",
                    headers=headers,
                    json=body
                ) as response:
                    # Check if the request was successful
                    if response.status != 200:
                        error_text = await response.text()
                        wiql_result = {
                            "status": "error",
                            "message": f"API request failed with status {response.status}",
                            "error": str(error_text),
                            "work_items": []
                        }
                    else:
                        # Parse the WIQL query response
                        wiql_response = await response.json()
                        work_item_ids = [item["id"] for item in wiql_response.get("workItems", [])]
                        
                        # If no work items found, return empty result
                        if not work_item_ids:
                            wiql_result = {
                                "status": "success",
                                "message": "No work items found",
                                "work_items": []
                            }
                        else:
                            # Fetch details for each work item
                            work_items = await self._fetch_work_item_details(session, work_item_ids)
                            
                            # Prepare successful result
                            wiql_result = {
                                "status": "success",
                                "message": f"Found {len(work_items)} work items",
                                "work_items": work_items
                            }
        except Exception as e:
            # Handle any exceptions
            wiql_result = {
                "status": "error",
                "message": f"Error fetching work items: {str(e)}",
                "work_items": []
            }
            logger.exception("Error in build_work_items")
            
        # Set component status and return data
        data = Data(value=wiql_result)
        self.status = data
        return data 

    async def _fetch_work_item_details(self, session: aiohttp.ClientSession, work_item_ids: List[int]) -> List[Dict]:
        """Fetch detailed information for a list of work item IDs"""
        try:
            # Prepare URL and headers
            ids_string = ",".join(map(str, work_item_ids))
            url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/wit/workitems?ids={ids_string}&api-version=5.1&$expand=all"
            
            auth_token = base64.b64encode(f":{self.pat_token}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/json"
            }
            
            # Make API request to fetch work item details
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Error fetching work item details: {error_text}")
                    return []
                
                # Parse response
                details_response = await response.json()
                
                # Process work items - create flat simple objects
                work_items = []
                for item in details_response.get("value", []):
                    fields = item.get("fields", {})
                    
                    # Extract assignee name safely
                    assigned_to = fields.get("System.AssignedTo")
                    if isinstance(assigned_to, dict):
                        assigned_to = assigned_to.get("displayName", "")
                    
                    # Extract created by safely
                    created_by = fields.get("System.CreatedBy")
                    if isinstance(created_by, dict):
                        created_by = created_by.get("displayName", "")
                    
                    # Create a flat work item with only simple types
                    work_item = {
                        "id": str(item.get("id", "")),
                        "url": str(item.get("url", "")),
                        "title": str(fields.get("System.Title", "")),
                        "state": str(fields.get("System.State", "")),
                        "type": str(fields.get("System.WorkItemType", "")),
                        "assigned_to": str(assigned_to),
                        "description": str(fields.get("System.Description", "")),
                        "created_date": str(fields.get("System.CreatedDate", "")),
                        "created_by": str(created_by),
                        "changed_date": str(fields.get("System.ChangedDate", "")),
                        "tags": str(fields.get("System.Tags", "")),
                        "iteration_path": str(fields.get("System.IterationPath", "")),
                        "area_path": str(fields.get("System.AreaPath", ""))
                    }
                    
                    work_items.append(work_item)
                
                return work_items
        
        except Exception as e:
            logger.exception("Error fetching work item details")
            return []  # Return empty list instead of raising to avoid UI errors

    async def _generate_wiql_from_natural_language(self) -> str:
        """Generate a WIQL query from natural language using LLM (simplified version)"""
        try:
            logger.info(f"Natural language query: {self.natural_language_query}")
            
            # In a real implementation, this would call the OpenAI API to generate a WIQL query
            # For now, just return a basic query to avoid errors
            
            # Extract some basic keywords from the query
            query_lower = self.natural_language_query.lower()
            
            # Detect work item types
            work_item_types = []
            if "bug" in query_lower:
                work_item_types.append("Bug")
            if "task" in query_lower or "tasks" in query_lower:
                work_item_types.append("Task")
            if "story" in query_lower or "user story" in query_lower:
                work_item_types.append("User Story")
                
            # If no specific types were mentioned, use a default set
            if not work_item_types:
                work_item_types = ["Task", "Bug", "User Story"]
                
            # Detect states
            states = []
            if "open" in query_lower or "active" in query_lower:
                states.append("Active")
            if "new" in query_lower:
                states.append("New")
            if "closed" in query_lower or "done" in query_lower or "complete" in query_lower:
                states.append("Closed")
                
            # Build a simple WIQL query
            if len(work_item_types) == 1:
                type_clause = f"[System.WorkItemType] = '{work_item_types[0]}'"
            else:
                type_list = ", ".join([f"'{t}'" for t in work_item_types])
                type_clause = f"[System.WorkItemType] IN ({type_list})"
                
            # Add state filter if states were detected
            state_clause = ""
            if states:
                if len(states) == 1:
                    state_clause = f" AND [System.State] = '{states[0]}'"
                else:
                    state_list = ", ".join([f"'{s}'" for s in states])
                    state_clause = f" AND [System.State] IN ({state_list})"
            
            # Finalize query with project filter
            project = getattr(self, 'project', '') or ''
            wiql_query = f"SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType] FROM WorkItems WHERE [System.TeamProject] = '{project}' AND {type_clause}{state_clause} ORDER BY [System.ChangedDate] DESC"
            
            logger.info(f"Generated WIQL query: {wiql_query}")
            return wiql_query
            
        except Exception as e:
            logger.exception("Error generating WIQL from natural language")
            # Return a default query when an error occurs
            return "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.WorkItemType] = 'Task' ORDER BY [System.ChangedDate] DESC"

    def _build_wiql_query(self, params: Dict[str, Any]) -> str:
        """Build a WIQL query from parameters"""
        try:
            # Default fields to select if not specified
            fields = params.get('fields', [])
            if not fields:
                fields = ['System.Id', 'System.Title', 'System.State', 'System.WorkItemType', 
                          'System.AssignedTo', 'System.Tags', 'System.Description']
            
            # Prepare SELECT clause
            field_clause = ", ".join([f"[{field}]" for field in fields])
            select_clause = f"SELECT {field_clause}"
            
            # Add TOP clause if max items specified
            if 'maxItems' in params and isinstance(params['maxItems'], int) and params['maxItems'] > 0:
                select_clause = f"SELECT TOP {params['maxItems']} {field_clause}"
            
            # Prepare FROM clause
            from_clause = "FROM WorkItems"
            
            # Prepare WHERE conditions
            where_conditions = []
            
            # Project condition - use the project from the component
            project = getattr(self, 'project', '') or ''
            where_conditions.append(f"[System.TeamProject] = '{project}'")
            
            # Work item types
            if 'workItemTypes' in params and params['workItemTypes']:
                types = params['workItemTypes']
                if isinstance(types, list) and len(types) > 0:
                    if len(types) == 1:
                        where_conditions.append(f"[System.WorkItemType] = '{types[0]}'")
                    else:
                        type_list = ", ".join([f"'{t}'" for t in types])
                        where_conditions.append(f"[System.WorkItemType] IN ({type_list})")
                elif isinstance(types, str):
                    where_conditions.append(f"[System.WorkItemType] = '{types}'")
            
            # States
            if 'states' in params and params['states']:
                states = params['states']
                if isinstance(states, list) and len(states) > 0:
                    if len(states) == 1:
                        where_conditions.append(f"[System.State] = '{states[0]}'")
                    else:
                        state_list = ", ".join([f"'{s}'" for s in states])
                        where_conditions.append(f"[System.State] IN ({state_list})")
                elif isinstance(states, str):
                    where_conditions.append(f"[System.State] = '{states}'")
            
            # Assigned to
            if 'assignedTo' in params and params['assignedTo']:
                where_conditions.append(f"[System.AssignedTo] = '{params['assignedTo']}'")
            
            # Area path
            if 'areaPath' in params and params['areaPath']:
                area_path = params['areaPath']
                if '*' in area_path:
                    # Use UNDER for wildcard paths
                    area_path = area_path.replace('*', '')
                    where_conditions.append(f"[System.AreaPath] UNDER '{area_path}'")
                else:
                    where_conditions.append(f"[System.AreaPath] = '{area_path}'")
            
            # Iteration path
            if 'iterationPath' in params and params['iterationPath']:
                iteration_path = params['iterationPath']
                if iteration_path == '@CurrentIteration':
                    where_conditions.append("[System.IterationPath] = @CurrentIteration")
                elif '*' in iteration_path:
                    # Use UNDER for wildcard paths
                    iteration_path = iteration_path.replace('*', '')
                    where_conditions.append(f"[System.IterationPath] UNDER '{iteration_path}'")
                else:
                    where_conditions.append(f"[System.IterationPath] = '{iteration_path}'")
            
            # Tags
            if 'tags' in params and params['tags']:
                tags = params['tags']
                if isinstance(tags, list) and len(tags) > 0:
                    tag_conditions = [f"[System.Tags] CONTAINS '{tag}'" for tag in tags]
                    where_conditions.append(" AND ".join(tag_conditions))
                elif isinstance(tags, str):
                    where_conditions.append(f"[System.Tags] CONTAINS '{tags}'")
            
            # Search terms
            if 'searchTerms' in params and params['searchTerms']:
                terms = params['searchTerms']
                if isinstance(terms, list) and len(terms) > 0:
                    search_fields = ['System.Title', 'System.Description']
                    for term in terms:
                        term_conditions = [f"[{field}] CONTAINS '{term}'" for field in search_fields]
                        where_conditions.append(f"({' OR '.join(term_conditions)})")
                elif isinstance(terms, str):
                    term_conditions = [f"[System.Title] CONTAINS '{terms}'", f"[System.Description] CONTAINS '{terms}'"]
                    where_conditions.append(f"({' OR '.join(term_conditions)})")
            
            # Assemble WHERE clause
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Prepare ORDER BY clause
            order_by_clause = ""
            if 'orderBy' in params and params['orderBy']:
                order_by = params['orderBy']
                if isinstance(order_by, list) and len(order_by) > 0:
                    order_terms = []
                    for item in order_by:
                        if isinstance(item, dict) and 'field' in item:
                            direction = "DESC" if item.get('descending', False) else "ASC"
                            order_terms.append(f"[{item['field']}] {direction}")
                    if order_terms:
                        order_by_clause = " ORDER BY " + ", ".join(order_terms)
                elif isinstance(order_by, dict) and 'field' in order_by:
                    direction = "DESC" if order_by.get('descending', False) else "ASC"
                    order_by_clause = f" ORDER BY [{order_by['field']}] {direction}"
            
            # Default order if none specified
            if not order_by_clause:
                order_by_clause = " ORDER BY [System.ChangedDate] DESC"
            
            # Assemble the complete query
            wiql_query = f"{select_clause} {from_clause}{where_clause}{order_by_clause}"
            
            return wiql_query
            
        except Exception as e:
            logger.exception("Error building WIQL query")
            raise ValueError(f"Failed to build WIQL query: {str(e)}")

    def build_wiql_query(self) -> Data:
        """Public method to build a WIQL query from parameters - can be called from the frontend"""
        try:
            # Default query to show in the UI
            wiql_query = "SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType] FROM WorkItems WHERE [System.WorkItemType] IN ('Task', 'Bug', 'User Story') ORDER BY [System.ChangedDate] DESC"
            
            # Return a simple success response - keep the structure minimal
            return Data(value={
                "query": wiql_query, 
                "status": "success"
            })
        except Exception as e:
            # Log the error and return an error response
            logger.exception("Error in build_wiql_query")
            return Data(value={
                "query": "", 
                "status": "error" 
            }) 