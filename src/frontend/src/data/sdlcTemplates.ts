import { FlowType } from '../types/flow';
import { api } from '../controllers/API/api';
import { getURL } from '../controllers/API/helpers/constants';

// The flow ID of the custom Business Analyst template
const CUSTOM_BA_TEMPLATE_ID = "116f1ecf-3ded-4a5e-9f3b-5bd3ba32d5a4";

/**
 * Function to fetch the custom Business Analyst template
 * This allows dynamically loading the user's template instead of using the static one
 */
export async function fetchBusinessAnalystTemplate(): Promise<FlowType | null> {
  try {
    // Configure the API request
    const headers = {
      'x-api-key': 'sk-BJbjcfb6w4-g1P_QoAyKEKiLyPwhBWWLo68bBCKctfE'
    };

    // Make the API request to fetch the template
    const response = await api.get(`${getURL("FLOWS")}/${CUSTOM_BA_TEMPLATE_ID}`, { headers });

    // If successful, return the flow data
    if (response.status === 200) {
      return response.data;
    }

    console.error("Failed to fetch custom Business Analyst template");
    return null;
  } catch (error) {
    console.error("Error fetching custom Business Analyst template:", error);
    return null;
  }
}

/**
 * Business Analyst Agent Template
 *
 * This is the fallback template that will be used if the custom template fetch fails
 */
export const businessAnalystTemplate: FlowType = {
  name: "Business Analyst",
  description: "An AI agent that automates common business analysis tasks",
  is_component: false,
  tags: ["SDLC", "Requirements", "Agile"],
  user_id: "",
  folder_id: "",
  data: {
    nodes: [
      // Text Input
      {
        id: "prompt-input",
        type: "genericNode",
        position: { x: 100, y: 150 },
        data: {
          type: "TextInput",
          node: {
            display_name: "Requirements Input",
            description: "Enter your requirements or questions",
            base_classes: ["TextInput"],
            template: {
              text: {
                type: "str",
                value: "",
                display_name: "Text",
                multiline: true,
                required: true
              }
            }
          }
        }
      },

      // Prompt Template for BA tasks
      {
        id: "prompt-template",
        type: "genericNode",
        position: { x: 400, y: 150 },
        data: {
          type: "PromptTemplate",
          node: {
            display_name: "BA Prompt Template",
            description: "Crafts prompts for business analysis tasks",
            base_classes: ["BasePromptTemplate"],
            template: {
              template: {
                type: "str",
                value: "You are an expert Business Analyst with extensive experience in software development, requirements gathering, and documentation. Your task is to help with the following business analysis request:\n\n{input}\n\nPlease provide a structured and comprehensive response focusing on:\n1. Understanding the business need\n2. Identifying key stakeholders\n3. Gathering requirements\n4. Analyzing and documenting requirements\n5. Validating requirements\n\nFormat your response in a clear, professional manner suitable for a business document.",
                display_name: "Template",
                multiline: true,
                required: true
              },
              input_variables: {
                type: "list",
                value: ["input"],
                display_name: "Input Variables",
                required: true
              }
            }
          }
        }
      },

      // LLM
      {
        id: "llm",
        type: "genericNode",
        position: { x: 700, y: 150 },
        data: {
          type: "ChatOpenAI",
          node: {
            display_name: "Business Analysis Engine",
            description: "Advanced LLM for business analysis tasks",
            base_classes: ["BaseChatModel"],
            template: {
              model_name: {
                type: "str",
                value: "gpt-4",
                display_name: "Model Name",
                required: true
              },
              temperature: {
                type: "float",
                value: 0.1,
                display_name: "Temperature",
                required: true
              }
            }
          }
        }
      },

      // Chat Output
      {
        id: "chat-output",
        type: "genericNode",
        position: { x: 1000, y: 150 },
        data: {
          type: "ChatOutput",
          node: {
            display_name: "Analysis Output",
            description: "Displays the analysis results",
            base_classes: ["BaseOutput"],
            template: {
              stream: {
                type: "boolean",
                value: true,
                display_name: "Stream Output"
              }
            }
          }
        }
      }
    ],

    // Simplified edges with minimal structure
    edges: [
      {
        id: "e1-2",
        source: "prompt-input",
        target: "prompt-template",
        sourceHandle: "output",
        targetHandle: "input",
        type: "default"
      },
      {
        id: "e2-3",
        source: "prompt-template",
        target: "llm",
        sourceHandle: "output",
        targetHandle: "input",
        type: "default"
      },
      {
        id: "e3-4",
        source: "llm",
        target: "chat-output",
        sourceHandle: "output",
        targetHandle: "input",
        type: "default"
      }
    ],

    // Viewport settings
    viewport: {
      zoom: 1,
      x: 0,
      y: 0
    }
  }
};

export default businessAnalystTemplate;
