"""Azure DevOps component for creating work items from text."""
from typing import Dict, List, Optional, Any, Union
from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, MultilineInput, DropdownInput, Output, BoolInput, IntInput
from langflow.schema import Data
import aiohttp
import base64
import json
import logging
import re
from enum import Enum

# Set up logger
logger = logging.getLogger(__name__)

class WorkItemType(str, Enum):
    USER_STORY = "User Story"
    BUG = "Bug"
    EPIC = "Epic"
    TASK = "Task"
    FEATURE = "Feature"
    ISSUE = "Issue"

class AzureDevOpsWriterComponent(Component):
    """A component that creates work items in Azure DevOps by extracting them from natural language text"""
    
    display_name: str = "Azure DevOps Work Item Creator"
    description: str = "Creates work items in Azure DevOps by extracting them from natural language text"
    documentation: str = "https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/"
    category: str = "sdlc"
    icon: str = "GitPullRequest"
    name: str = "AzureDevOpsWriterComponent"
    
    def __init__(self, **kwargs):
        try:
            # Initialize with the base Component class first
            super().__init__(**kwargs)
            
            # Set minimal metadata
            self._metadata = {
                "display_name": str(self.display_name),
                "description": str(self.description),
                "icon": str(self.icon),
                "category": str(self.category),
                "version": "1.0.0"
            }
            
            # Initialize default attributes
            self._set_default_attributes()
            
            logger.info("AzureDevOpsWriterComponent initialized successfully")
        except Exception as e:
            logger.exception(f"Error initializing AzureDevOpsWriterComponent: {e}")
            
    def _set_default_attributes(self):
        """Set default values for attributes to prevent undefined errors in frontend"""
        if not hasattr(self, 'organization'):
            self.organization = ""
        if not hasattr(self, 'project'):
            self.project = ""
        if not hasattr(self, 'pat_token'):
            self.pat_token = ""
        if not hasattr(self, 'work_item_type'):
            self.work_item_type = WorkItemType.USER_STORY.value
        if not hasattr(self, 'input_text'):
            self.input_text = ""
        if not hasattr(self, 'openai_api_key'):
            self.openai_api_key = ""
        if not hasattr(self, 'model'):
            self.model = "gpt-3.5-turbo"
        if not hasattr(self, 'area_path'):
            self.area_path = ""
        if not hasattr(self, 'iteration_path'):
            self.iteration_path = ""
    
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
        DropdownInput(
            name="work_item_type",
            display_name="Work Item Type",
            required=True,
            options=[t.value for t in WorkItemType],
            value=WorkItemType.USER_STORY.value,
            helper_text="Type of work items to extract and create"
        ),
        MultilineInput(
            name="input_text",
            display_name="Input Text",
            required=True,
            placeholder="Enter text containing user stories, bugs, or other work items...",
            helper_text="Free text containing work items to be extracted and created"
        ),
        StrInput(
            name="area_path",
            display_name="Area Path",
            required=False,
            placeholder="Project\\Area",
            helper_text="Area path for the work items (leave empty for default)"
        ),
        StrInput(
            name="iteration_path",
            display_name="Iteration Path",
            required=False,
            placeholder="Project\\Iteration",
            helper_text="Iteration path for the work items (leave empty for default)"
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            required=True,
            placeholder="sk-...",
            helper_text="OpenAI API key for extracting work items from text"
        ),
        StrInput(
            name="model",
            display_name="LLM Model",
            required=False,
            value="gpt-3.5-turbo",
            placeholder="gpt-3.5-turbo",
            helper_text="The LLM model to use for extracting work items"
        ),
    ]
    
    outputs = [
        Output(display_name="Created Work Items", name="created_work_items", method="create_work_items"),
        Output(display_name="Extracted Work Items", name="extracted_work_items", method="extract_work_items"),
    ]

    async def create_work_items(self) -> Data:
        """Extract work items from text and create them in Azure DevOps"""
        try:
            # Validate required inputs
            for required_attr in ['organization', 'project', 'pat_token', 'input_text', 'openai_api_key']:
                if not hasattr(self, required_attr) or not getattr(self, required_attr):
                    result = {
                        "status": "error",
                        "message": f"Missing required parameter: {required_attr}",
                        "created_items": []
                    }
                    return Data(value=result)
            
            # Extract work items from text
            extracted_items = await self._extract_work_items_with_llm()
            
            if not extracted_items:
                result = {
                    "status": "warning",
                    "message": f"No {self.work_item_type} items were extracted from the input text",
                    "created_items": []
                }
                return Data(value=result)
            
            # Create work items in Azure DevOps
            created_items = await self._create_work_items_in_azure_devops(extracted_items)
            
            # Prepare result
            if not created_items:
                result = {
                    "status": "error",
                    "message": "Failed to create work items in Azure DevOps",
                    "extracted_items": extracted_items,
                    "created_items": []
                }
            else:
                result = {
                    "status": "success",
                    "message": f"Successfully created {len(created_items)} {self.work_item_type} items",
                    "extracted_items": extracted_items,
                    "created_items": created_items
                }
            
        except Exception as e:
            logger.exception("Error in create_work_items")
            result = {
                "status": "error",
                "message": f"Error creating work items: {str(e)}",
                "created_items": []
            }
            
        # Set component status and return data
        data = Data(value=result)
        self.status = data
        return data

    async def extract_work_items(self) -> Data:
        """Extract work items from text without creating them in Azure DevOps"""
        try:
            # Validate required inputs
            if not hasattr(self, 'input_text') or not self.input_text:
                result = {
                    "status": "error",
                    "message": "Missing required input text",
                    "extracted_items": []
                }
                return Data(value=result)
            
            if not hasattr(self, 'openai_api_key') or not self.openai_api_key:
                result = {
                    "status": "error",
                    "message": "Missing required OpenAI API key",
                    "extracted_items": []
                }
                return Data(value=result)
                
            # Extract work items from text
            extracted_items = await self._extract_work_items_with_llm()
            
            if not extracted_items:
                result = {
                    "status": "warning",
                    "message": f"No {self.work_item_type} items were extracted from the input text",
                    "extracted_items": []
                }
            else:
                result = {
                    "status": "success",
                    "message": f"Successfully extracted {len(extracted_items)} {self.work_item_type} items",
                    "extracted_items": extracted_items
                }
                
        except Exception as e:
            logger.exception("Error in extract_work_items")
            result = {
                "status": "error",
                "message": f"Error extracting work items: {str(e)}",
                "extracted_items": []
            }
            
        # Set component status and return data
        data = Data(value=result)
        self.status = data
        return data

    async def _extract_work_items_with_llm(self) -> List[Dict[str, str]]:
        """Use LLM to extract work items from text"""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)
            
            # Determine prompt based on work item type
            system_prompt = f"""
            You are an expert in extracting {self.work_item_type} items from text. 
            Extract all {self.work_item_type} items from the provided text.
            For each item, identify the title and description.
            """
            
            user_prompt = f"""
            Extract all {self.work_item_type} items from the following text. 
            Return them as a structured list with title and description for each item.
            Text: {self.input_text}
            """
            
            # Call OpenAI API with function calling
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                functions=[{
                    "name": "extract_work_items",
                    "description": f"Extract {self.work_item_type} items from the input text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {
                                            "type": "string",
                                            "description": f"The title of the {self.work_item_type}"
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": f"The description of the {self.work_item_type}"
                                        },
                                        "acceptance_criteria": {
                                            "type": "string",
                                            "description": "Acceptance criteria for the work item (if applicable)"
                                        },
                                        "priority": {
                                            "type": "string",
                                            "description": "Priority level of the work item (if mentioned)"
                                        },
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Tags associated with the work item (if mentioned)"
                                        }
                                    },
                                    "required": ["title", "description"]
                                }
                            }
                        },
                        "required": ["items"]
                    }
                }],
                function_call={"name": "extract_work_items"}
            )
            
            # Parse function call response
            function_call = response.choices[0].message.function_call
            if function_call and function_call.arguments:
                try:
                    args = json.loads(function_call.arguments)
                    extracted_items = args.get("items", [])
                    logger.info(f"Extracted {len(extracted_items)} {self.work_item_type} items from text")
                    return extracted_items
                except json.JSONDecodeError as e:
                    logger.exception(f"Error parsing function call response: {e}")
                    return []
            
            return []
                
        except Exception as e:
            logger.exception(f"Error extracting work items with LLM: {e}")
            return []

    async def _create_work_items_in_azure_devops(self, work_items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Create work items in Azure DevOps"""
        created_items = []
        
        try:
            # Prepare authentication for Azure DevOps API
            auth_token = base64.b64encode(f":{self.pat_token}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/json-patch+json"
            }
            
            # Process each work item
            async with aiohttp.ClientSession() as session:
                for item in work_items:
                    try:
                        # Prepare API URL
                        url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/wit/workitems/${self.work_item_type.replace(' ', '%20')}?api-version=6.0"
                        
                        # Prepare document operations for creating work item
                        operations = [
                            {
                                "op": "add",
                                "path": "/fields/System.Title",
                                "value": item["title"]
                            },
                            {
                                "op": "add",
                                "path": "/fields/System.Description",
                                "value": item["description"]
                            }
                        ]
                        
                        # Add area path if provided
                        if hasattr(self, 'area_path') and self.area_path:
                            operations.append({
                                "op": "add",
                                "path": "/fields/System.AreaPath",
                                "value": self.area_path
                            })
                            
                        # Add iteration path if provided
                        if hasattr(self, 'iteration_path') and self.iteration_path:
                            operations.append({
                                "op": "add",
                                "path": "/fields/System.IterationPath",
                                "value": self.iteration_path
                            })
                        
                        # Add acceptance criteria if provided (primarily for User Stories)
                        if "acceptance_criteria" in item and item["acceptance_criteria"]:
                            operations.append({
                                "op": "add",
                                "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
                                "value": item["acceptance_criteria"]
                            })
                            
                        # Add priority if provided
                        if "priority" in item and item["priority"]:
                            # Try to convert priority string to a number
                            try:
                                priority_value = self._parse_priority(item["priority"])
                                operations.append({
                                    "op": "add",
                                    "path": "/fields/Microsoft.VSTS.Common.Priority",
                                    "value": priority_value
                                })
                            except ValueError:
                                # Skip priority if we can't parse it
                                pass
                                
                        # Add tags if provided
                        if "tags" in item and item["tags"] and isinstance(item["tags"], list):
                            tags_value = "; ".join(item["tags"])
                            operations.append({
                                "op": "add",
                                "path": "/fields/System.Tags",
                                "value": tags_value
                            })
                        
                        # Make API request to create work item
                        async with session.post(url, headers=headers, json=operations) as response:
                            if response.status == 200:
                                work_item_response = await response.json()
                                created_item = {
                                    "id": work_item_response.get("id"),
                                    "url": work_item_response.get("url"),
                                    "title": item["title"],
                                    "type": self.work_item_type
                                }
                                created_items.append(created_item)
                                logger.info(f"Created {self.work_item_type} with ID {created_item['id']}")
                            else:
                                error_text = await response.text()
                                logger.error(f"Failed to create work item: {error_text}")
                    except Exception as e:
                        logger.exception(f"Error creating single work item: {e}")
        
        except Exception as e:
            logger.exception(f"Error creating work items in Azure DevOps: {e}")
            
        return created_items
    
    def _parse_priority(self, priority_string: str) -> int:
        """Parse priority string to an integer value (1-4)"""
        priority_string = priority_string.lower()
        
        # Check for numeric priority
        if priority_string.isdigit():
            priority = int(priority_string)
            if 1 <= priority <= 4:
                return priority
        
        # Check for text-based priority
        if "critical" in priority_string or "highest" in priority_string:
            return 1
        elif "high" in priority_string:
            return 2
        elif "medium" in priority_string or "normal" in priority_string:
            return 3
        elif "low" in priority_string or "lowest" in priority_string:
            return 4
            
        # Default to normal priority
        return 3 