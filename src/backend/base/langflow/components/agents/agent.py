from langchain_core.tools import StructuredTool
from typing import Any, Dict, List, Optional

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.base.agents.events import ExceptionWithMessageError
from langflow.base.models.model_input_constants import (
    MODEL_DYNAMIC_UPDATE_FIELDS,
    MODEL_PROVIDERS_DICT,
    MODELS_METADATA,
)
from langflow.base.models.model_utils import get_model_name
from langflow.base.outputs.structured_output import StructuredOutput
from langflow.components.helpers import CurrentDateComponent
from langflow.components.helpers.memory import MemoryComponent
from langflow.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from langflow.custom.custom_component.component import _get_component_toolkit
from langflow.custom.utils import update_component_build_config
from langflow.field_typing import Tool
from langflow.interface.input.inputs import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
    StrInput,
)
from langflow.interface.output import Output
from langflow.logging import logger
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message
from langflow.base.common.models import Document, Messages
from langflow.base.common.typed_dicts import ModelResult


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


class AgentComponent(ToolCallingAgentComponent):
    display_name: str = "Agent"
    description: str = "Define the agent's instructions, then enter a task to complete using tools."
    icon = "bot"
    beta = False
    name = "Agent"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            info="The provider of the language model that the agent will use to generate responses.",
            options=[*sorted(MODEL_PROVIDERS_DICT.keys()), "Custom"],
            value="OpenAI",
            real_time_refresh=True,
            input_types=[],
            options_metadata=[MODELS_METADATA[key] for key in sorted(MODELS_METADATA.keys())] + [{"icon": "brain"}],
        ),
        *MODEL_PROVIDERS_DICT["OpenAI"]["inputs"],
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
            advanced=False,
        ),
        *LCToolsAgentComponent._base_inputs,
        *memory_inputs,
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
    ]
    outputs = [Output(name="response", display_name="Response", method="message_response")]

    async def message_response(self) -> Message:
        try:
            # Get LLM model and validate
            llm_model, display_name = self.get_llm()
            if llm_model is None:
                msg = "No language model selected. Please choose a model to proceed."
                raise ValueError(msg)
            self.model_name = get_model_name(llm_model, display_name=display_name)

            # Get memory data
            self.chat_history = await self.get_memory_data()

            # Add current date tool if enabled
            if self.add_current_date_tool:
                if not isinstance(self.tools, list):  # type: ignore[has-type]
                    self.tools = []
                current_date_tool = (await CurrentDateComponent(**self.get_base_args()).to_toolkit()).pop(0)
                if not isinstance(current_date_tool, StructuredTool):
                    msg = "CurrentDateComponent must be converted to a StructuredTool"
                    raise TypeError(msg)
                self.tools.append(current_date_tool)

            # Validate tools
            if not self.tools:
                msg = "Tools are required to run the agent. Please add at least one tool."
                raise ValueError(msg)

            # Set up and run agent
            self.set(
                llm=llm_model,
                tools=self.tools,
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self.system_prompt,
            )
            agent = self.create_agent_runnable()
            return await self.run_agent(agent)

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"{type(e).__name__}: {e!s}")
            raise
        except ExceptionWithMessageError as e:
            logger.error(f"ExceptionWithMessageError occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e!s}")
            raise

    async def get_memory_data(self):
        memory_kwargs = {
            component_input.name: getattr(self, f"{component_input.name}") for component_input in self.memory_inputs
        }
        # filter out empty values
        memory_kwargs = {k: v for k, v in memory_kwargs.items() if v}

        return await MemoryComponent(**self.get_base_args()).set(**memory_kwargs).retrieve_messages()

    def get_llm(self):
        if not isinstance(self.agent_llm, str):
            return self.agent_llm, None

        try:
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if not provider_info:
                msg = f"Invalid model provider: {self.agent_llm}"
                raise ValueError(msg)

            component_class = provider_info.get("component_class")
            display_name = component_class.display_name
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix", "")

            return self._build_llm_model(component_class, inputs, prefix), display_name

        except Exception as e:
            logger.error(f"Error building {self.agent_llm} language model: {e!s}")
            msg = f"Failed to initialize language model: {e!s}"
            raise ValueError(msg) from e

    def _build_llm_model(self, component, inputs, prefix=""):
        model_kwargs = {input_.name: getattr(self, f"{prefix}{input_.name}") for input_ in inputs}
        return component.set(**model_kwargs).build_model()

    def set_component_params(self, component):
        provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
        if provider_info:
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix")
            model_kwargs = {input_.name: getattr(self, f"{prefix}{input_.name}") for input_ in inputs}

            return component.set(**model_kwargs)
        return component

    def delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        """Delete fields from build_config."""
        if isinstance(fields, list):
            for field in fields:
                if field in build_config:
                    del build_config[field]
        elif isinstance(fields, dict):
            for field in fields:
                if field in build_config:
                    del build_config[field]

    def update_input_types(self, build_config: dotdict) -> dotdict:
        """Update input types for all fields in build_config."""
        for key, value in build_config.items():
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        # Iterate over all providers in the MODEL_PROVIDERS_DICT
        if field_name == "agent_llm" and field_value in MODEL_PROVIDERS_DICT:
            # Create a map of provider -> (fields_to_add, fields_to_delete)
            provider_configs = {
                provider: (
                    MODEL_PROVIDERS_DICT[provider]["inputs"],
                    [
                        MODEL_PROVIDERS_DICT[other_provider]["fields"]
                        for other_provider in MODEL_PROVIDERS_DICT
                        if other_provider != provider
                    ],
                )
                for provider in MODEL_PROVIDERS_DICT
            }
            if field_value in provider_configs:
                fields_to_add, fields_to_delete = provider_configs[field_value]

                # Delete fields from other providers
                for fields in fields_to_delete:
                    self.delete_fields(build_config, fields)

                # Add provider-specific fields
                if field_value == "OpenAI" and not any(field in build_config for field in fields_to_add):
                    build_config.update(fields_to_add)
                else:
                    build_config.update(fields_to_add)
                # Reset input types for agent_llm
                build_config["agent_llm"]["input_types"] = []
            elif field_value == "Custom":
                # Import ALL_PROVIDER_FIELDS here to avoid circular imports
                from langflow.base.models.model_input_constants import ALL_PROVIDER_FIELDS
                # Delete all provider fields
                self.delete_fields(build_config, ALL_PROVIDER_FIELDS)
                # Update with custom component
                custom_component = DropdownInput(
                    name="agent_llm",
                    display_name="Language Model",
                    options=[*sorted(MODEL_PROVIDERS_DICT.keys()), "Custom"],
                    value="Custom",
                    real_time_refresh=True,
                    input_types=["LanguageModel"],
                    options_metadata=[MODELS_METADATA[key] for key in sorted(MODELS_METADATA.keys())]
                    + [{"icon": "brain"}],
                )
                build_config.update({"agent_llm": custom_component.to_dict()})
            # Update input types for all fields
            build_config = self.update_input_types(build_config)

            # Validate required keys
            default_keys = [
                "code",
                "_type",
                "agent_llm",
                "tools",
                "input_value",
                "add_current_date_tool",
                "system_prompt",
                "agent_description",
                "max_iterations",
                "handle_parsing_errors",
                "verbose",
            ]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
        if (
            isinstance(self.agent_llm, str)
            and self.agent_llm in MODEL_PROVIDERS_DICT
            and field_name in MODEL_DYNAMIC_UPDATE_FIELDS
        ):
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if provider_info:
                component_class = provider_info.get("component_class")
                component_class = self.set_component_params(component_class)
                prefix = provider_info.get("prefix")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call each component class's update_build_config method
                    # remove the prefix from the field_name
                    if isinstance(field_name, str) and isinstance(prefix, str):
                        field_name = field_name.replace(prefix, "")
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, "model_name"
                    )
        return dotdict({k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in build_config.items()})

    async def to_toolkit(self) -> list[Tool]:
        component_toolkit = _get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        # TODO: Agent Description Depreciated Feature to be removed
        description = f"{agent_description}{tools_names}"
        tools = component_toolkit(component=self).get_tools(
            tool_name=self.get_tool_name(), tool_description=description, callbacks=self.get_langchain_callbacks()
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)
        return tools

    def build_config(self):
        """Build a config for the component."""
        # Use dotdict to enable dot notation for the config
        build_config = dotdict()
        build_config.fields = {}
        # Initialize fields based on model
        field_classes = MODEL_PROVIDERS_DICT.get("agent")

        if field_classes:
            if self.description is not None:
                build_config.description = self.description

            if hasattr(self, "update_dynamic_fields"):
                fields_types = MODEL_DYNAMIC_UPDATE_FIELDS
                if field_classes:
                    for field in field_classes:
                        field_clone = field.copy() if field and isinstance(field, dict) else {}
                        if field_clone.get("name") in fields_types:
                            field_clone = self.update_dynamic_fields(
                                field, self.dynamic_config.get(field["name"]) or {}
                            )

                        build_config.fields[field_clone.get("name")] = field_clone
            else:
                for field in field_classes:
                    build_config.fields[field.get("name")] = field

            # Import ALL_PROVIDER_FIELDS here to avoid circular imports
            from langflow.base.models.model_input_constants import ALL_PROVIDER_FIELDS
            self.delete_fields(build_config, ALL_PROVIDER_FIELDS)

        return build_config
