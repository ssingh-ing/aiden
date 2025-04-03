"""Langflow components."""
import importlib
import json
import os
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger
from pydantic.v1 import BaseModel, Field

from langflow.api.v1.schemas import InputType
from langflow.components.agents import agent_components
from langflow.components.audio import audio_components
from langflow.components.chains import chain_components
from langflow.components.chains import DEFAULT_RESPONSE
from langflow.components.chat import chat_components
from langflow.components.code_interpreter import code_interpreter_components
from langflow.components.datastores import datastore_components
from langflow.components.documentloaders import documentloader_components
from langflow.components.embeddings import embedding_components
from langflow.components.google import google_components
from langflow.components.llms import llm_components
from langflow.components.memories import memory_components
from langflow.components.output_parsers import output_parser_components
from langflow.components.output_parsers.boolean import BooleanOutputParser
from langflow.components.prompts import prompt_components
from langflow.components.retrievers import retriever_components
from langflow.components.sdlc import sdlc_components
from langflow.components.serializers import serializer_components
from langflow.components.sreops import sreops_components
from langflow.components.textsplitters import textsplitter_components
from langflow.components.vectorstores import vectorstore_components
from langflow.components.wrappers import wrapper_components

try:
    from langflow.components.context_builder import context_builder_components
except ImportError:
    # Set to empty list if import fails
    context_builder_components = []


# Assuming these imports work as they should
# if there are import errors, we need to fix the imports
# or add the appropriate fallbacks like the one above
def get_task_components():
    task_components = []
    try:
        from langflow.components.tasks import task_components
    except ImportError:
        # Set to empty list if import fails
        task_components = []
    return task_components


# Getting the directory of the current file
current_directory = os.path.dirname(os.path.realpath(__file__))

# Defining directories to search for yaml files
yaml_directories = [
    current_directory,  # For testing
]

# Looking for langchain_resources.yaml in specified directories
# and loading the first one found
COMPONENTS_REGISTRY = []
components_dict = {}

try:
    for directory in yaml_directories:
        file_path = os.path.join(directory, "langchain_resources.yaml")
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                components_dict = yaml.safe_load(file)
            COMPONENTS_REGISTRY.append(components_dict)
            break  # Stop after finding the first file

    if not COMPONENTS_REGISTRY or not components_dict:
        logger.warning(
            "No langchain_resources.yaml found in specified directories or file is empty."
        )
except Exception as error:
    logger.exception(error)
    logger.warning(
        "Error loading langchain_resources.yaml. Using default components registry."
    )


ARTIFACT_KEYS = {
    # "components": [],
    "results": [],
    "artifacts": ["image", "audio"],
}

CUSTOM_COMPONENT_REGISTRY = {}


def register_with_load_method(component):
    """
    Register a component with a load method
    """
    try:
        # Get component_class_name from component
        component_class_name = component.__name__
        # Get component_name from component
        component_name = component_class_name
        # Get component_type from component
        component_description = component.__doc__

        if not CUSTOM_COMPONENT_REGISTRY.get(component_name):
            # Add component to component_registry
            CUSTOM_COMPONENT_REGISTRY[component_name] = {
                component_name: component_name,
                "name": component_name,
                "description": component_description,
                "component": component,
            }
            logger.debug(f"Added component {component_name} to registry")
        else:
            logger.debug(f"Component {component_name} already in registry")
    except Exception as error:
        logger.exception(error)
        logger.warning(f"Error loading component {component}")


def load_components_registry():
    """
    The COMPONENTS_REGISTRY is a list of dictionaries, where each dictionary has the following keys:
    - name: the name of the component
    - description: a description of the component
    - component: a component class
    """
    try:
        for component_collection in [
            chat_components,
            agent_components,
            chain_components,
            documentloader_components,
            embedding_components,
            llm_components,
            memory_components,
            prompt_components,
            textsplitter_components,
            vectorstore_components,
            wrapper_components,
            datastore_components,
            retriever_components,
            code_interpreter_components,
            serializer_components,
            google_components,
            output_parser_components,
            audio_components,
            sdlc_components,
            sreops_components,
            *get_task_components(),
            *context_builder_components,
        ]:
            # Adding all components from the component collection to the registry
            # Component collection is a list of objects with a custom build_config method
            for component in component_collection:
                if hasattr(component, "build_config"):
                    CUSTOM_COMPONENT_REGISTRY[component.name] = component

        # Sort register by name
        CUSTOM_COMPONENT_REGISTRY_SORTED = dict(
            sorted(CUSTOM_COMPONENT_REGISTRY.items())
        )
        return CUSTOM_COMPONENT_REGISTRY_SORTED
    except Exception as error:
        logger.exception(error)
        logger.warning("Error loading components registry. Using default registry.")
        return {}


class BuildResponse(BaseModel):
    status: str = Field(None, description="Status of the build")


class ComponentNode(BaseModel):
    id: str = Field(None, description="ID of the node")
    node_id: str = Field(None, description="Node that will process the node")
    name: str = Field(None, description="Name of the node")
    style: Dict[str, Any] = Field(None, description="Style of the node")
    data: Dict[str, Any] = Field(None, description="Data of the node")
    node_type: str = Field(None, description="Type of the node")
    width: Optional[int] = Field(None, description="Width of the node")
    height: Optional[int] = Field(None, description="Height of the node")
    position: Dict[str, Any] = Field(None, description="Position of the node")
    fields_meta: Dict[str, Any] = Field({}, description="Fields meta of the node")
    selected: bool = Field(None, description="Whether the node is selected")
    dragging: bool = Field(None, description="Whether the node is being dragged")
    positionAbsolute: Dict[str, Any] = Field(
        None, description="Absolute position of the node"
    )
    class_name: str = Field(None, description="Class name of the node")
    inputs: Dict[str, Any] = Field(None, description="Inputs of the node")
    model: Dict[str, Any] = Field(None, description="Model of the node")
    inputs_format: Dict[str, InputType] = Field(
        None, description="Format of the inputs"
    )
    response: Optional[BuildResponse] = Field(None, description="Response of the build")
    is_component: bool = Field(False, description="Whether the node is a component")

    class Config:
        arbitrary_types_allowed = True
        schema_extra = {"example": {}}


class Component:
    """Base component class for Langflow component primitives."""

    # Used to define which component category this belongs to (e.g., llms, chains, agents, memories)
    display_name: str = ""
    description: str = ""
    documentation: str = ""
    beta: bool = False
    icon: str = ""
    name: str = ""
    category: str = ""
    status: str = ""
    custom: bool = False
    deprecated: bool = False
    is_component: bool = False
    version: str = "1.0.0"

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", None)
        self._base_classes = []
        self._status = kwargs.get("status", "")
        self._data = {}  # Used for internal data
        self._status_message = {}  # Used for status messages
        self._errors = {}  # Used for errors
        self._inputs = {}  # Used for inputs
        self._outputs = {}  # Used for outputs
        self._node_errors = []  # Used for node errors

        try:
            self._metadata = {
                "display_name": self.display_name or "",
                "description": self.description or "",
                "documentation": self.documentation or "",
                "beta": self.beta,
                "deprecated": self.deprecated,
                "is_component": self.is_component,
                "icon": self.icon or "",
                "name": self.name or "",
                "category": self.category or "",
                "status": self.status or "",
                "custom": self.custom,
                "version": self.version,
            }
        except Exception as error:
            logger.exception(error)
            self._metadata = {"error": str(error), "display_name": self.display_name}
            # Fallback to defaults if error
            self._inputs = {}
            self._outputs = {}

        # Used to define the component's code and output_types
        self.code = kwargs.get("code", None)
        self.output_types = kwargs.get("output_types", [])
        self._set_default_from_inputs()

    def _set_default_from_inputs(self):
        """Set default values from inputs."""
        for key, value in self.inputs.items():
            if isinstance(value, dict) and "value" in value:
                setattr(self, key, value["value"])
            else:
                setattr(self, key, value)

    @property
    def nodes(self):
        """Return a list of nodes."""
        return [ComponentNode(**{"name": self.name, "id": self.id, "data": self._data})]

    @property
    def base_classes(self) -> List[str]:
        """Return the base classes of the component."""
        return self._base_classes or []

    @property
    def metadata(self) -> Dict[str, Any]:
        """Return the metadata of the component."""
        return self._metadata or {}

    @property
    def inputs(self) -> Dict[str, Dict[str, Any]]:
        """Return the inputs of the component."""
        return self._inputs or {}

    @property
    def outputs(self) -> Dict[str, Dict[str, Any]]:
        """Return the outputs of the component."""
        return self._outputs or {}

    @property
    def status(self) -> str:
        """Return the status of the component."""
        return self._status or ""

    def process_errors(self, errors):
        """Process the errors of the component."""
        self._errors = errors


def load_component_from_file(
    file_path: str, update_component_registry: bool = False
) -> None:
    """
    Loads a component from a file and returns it.
    """
    try:
        # Check if the path exists
        if not os.path.exists(file_path):
            logger.error(f"The custom file path does not exist: {file_path}")
            return

        # Get the module name from the file path (dropping extension)
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        module_path = os.path.dirname(file_path)

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            logger.error(f"Could not load spec for module {module_name} from {file_path}")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for classes in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            try:
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Component)
                    and attr != Component
                ):
                    # We have found a component. Register it.
                    register_with_load_method(attr)
            except TypeError:
                # If attr isn't a class, issubclass() raises a TypeError
                continue
    except Exception as error:
        logger.exception(
            f"There was an error during loading the custom component: {error}; file_path: {file_path}",
            # Path of the file with the exception
            exc_path=file_path,
        )


COMPONENTS_REGISTRY = load_components_registry()
DEFAULT_COMPONENT_REGISTRY = COMPONENTS_REGISTRY
COMPONENT_LIST_SET = set()
for component_name, component in COMPONENTS_REGISTRY.items():
    if hasattr(component, "get_components_list"):
        COMPONENT_LIST_SET.update(component.get_components_list())
    else:
        COMPONENT_LIST_SET.add(component_name)

COMPONENT_LIST = sorted(list(COMPONENT_LIST_SET))

# Add BooleanOutputParser to handle boolean output
# This is a hack to get around the fact that we don't have a BooleanOutputParser
# in the registry. This is because the registry is built before the OutputParserComponent
# class is defined.
COMPONENTS_REGISTRY["BooleanOutputParser"] = BooleanOutputParser()
# Add it to the COMPONENT_LIST
COMPONENT_LIST.append("BooleanOutputParser")


__all__ = [
    "COMPONENTS_REGISTRY",
    "COMPONENT_LIST",
    "DEFAULT_COMPONENT_REGISTRY",
    "Component",
]
