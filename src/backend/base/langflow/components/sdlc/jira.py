"""Jira component for fetching issues."""
from typing import Dict, List, Optional, Any
from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, MultilineInput, DropdownInput, Output, IntInput, BoolInput
from langflow.schema import Data
import aiohttp
import base64
import json

class JiraComponent(Component):
    """A component that fetches issues from Jira using JQL queries"""
    
    display_name: str = "Jira Issues"
    description: str = "Fetches issues from Jira using JQL queries"
    documentation: str = "https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/"
    category: str = "sdlc"
    icon: str = "GitPullRequest"
    name: str = "JiraComponent"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Setting metadata for discovery
        self._metadata = {
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "icon": self.icon,
        }
    
    inputs = [
        StrInput(
            name="site_url",
            display_name="Jira Site URL",
            required=True,
            placeholder="https://your-domain.atlassian.net",
            helper_text="Your Jira site URL"
        ),
        StrInput(
            name="username",
            display_name="Username/Email",
            required=True,
            placeholder="your-email@example.com",
            helper_text="Your Jira username or email address"
        ),
        SecretStrInput(
            name="api_token",
            display_name="API Token",
            required=True,
            placeholder="your-api-token",
            helper_text="Your Jira API token (create in Atlassian account settings)"
        ),
        MultilineInput(
            name="jql_query",
            display_name="JQL Query",
            required=True,
            placeholder="project = PROJ AND status = 'In Progress'",
            value="project = PROJ AND status = 'In Progress'",
            helper_text="Jira Query Language (JQL) query to execute"
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            required=False,
            value=50,
            helper_text="Maximum number of issues to return (default: 50)"
        ),
        BoolInput(
            name="include_fields",
            display_name="Include Fields",
            value=True,
            helper_text="Whether to include detailed fields in the results"
        ),
        MultilineInput(
            name="fields",
            display_name="Fields",
            required=False,
            value="summary,status,assignee,priority,created,updated",
            helper_text="Comma-separated list of fields to include in the results"
        )
    ]
    
    outputs = [
        Output(display_name="Issues", name="issues", method="build_issues"),
    ]

    async def build_issues(self) -> Data:
        """Build the issues output."""
        try:
            # Ensure site URL has no trailing slash
            site_url = self.site_url.rstrip('/')
            
            # Create search API endpoint URL
            search_url = f"{site_url}/rest/api/3/search"
            
            # Prepare basic authentication
            auth_token = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Prepare request parameters
            params = {
                "jql": self.jql_query,
                "maxResults": self.max_results
            }
            
            # Add fields if specified
            if self.include_fields and hasattr(self, 'fields') and self.fields:
                params["fields"] = [field.strip() for field in self.fields.split(",")]
                
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    search_url,
                    headers=headers,
                    json=params
                ) as response:
                    # Check if the request was successful
                    if response.status != 200:
                        error_text = await response.text()
                        result = {
                            "status": "error",
                            "message": f"API request failed with status {response.status}",
                            "details": error_text
                        }
                    else:
                        # Parse the response
                        api_result = await response.json()
                        
                        # Process and structure the results
                        result = {
                            "total": api_result.get("total", 0),
                            "issues_count": len(api_result.get("issues", [])),
                            "issues": api_result.get("issues", []),
                            "start_at": api_result.get("startAt", 0),
                            "max_results": api_result.get("maxResults", 0)
                        }
                        
                        # Add pagination information if available
                        if "startAt" in api_result and "maxResults" in api_result and "total" in api_result:
                            result["pagination"] = {
                                "page": (api_result["startAt"] // api_result["maxResults"]) + 1,
                                "total_pages": (api_result["total"] + api_result["maxResults"] - 1) // api_result["maxResults"],
                                "has_more": (api_result["startAt"] + api_result["maxResults"]) < api_result["total"]
                            }
                            
        except Exception as e:
            # Return a structured error response
            result = {
                "status": "error",
                "message": f"Error fetching Jira issues: {str(e)}",
                "exception_type": type(e).__name__
            }
            
        # Set component status and return data
        data = Data(value=result)
        self.status = data
        return data 