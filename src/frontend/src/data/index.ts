import { businessAnalystTemplate, fetchBusinessAnalystTemplate } from './sdlcTemplates';

// Initialize cache for the custom BA template
let cachedBATemplate = null;

// Create a registry of all templates by category for easy access
export const templateRegistry = {
  sdlc: {
    "business-analyst": businessAnalystTemplate,
    // Add more SDLC templates as they are created
  },
  // Add more template categories as needed
};

// Function to fetch and update the Business Analyst template at runtime
export async function initializeTemplates() {
  try {
    // Fetch the custom Business Analyst template
    const customTemplate = await fetchBusinessAnalystTemplate();

    // If we successfully fetched the template, update the registry and cache
    if (customTemplate) {
      templateRegistry.sdlc["business-analyst"] = customTemplate;
      cachedBATemplate = customTemplate;
      console.log("Successfully loaded custom Business Analyst template");
    }
  } catch (error) {
    console.error("Error initializing templates:", error);
  }
}

// Get template by type and ID, with dynamic loading for the Business Analyst template
export function getTemplateByTypeAndId(type: string, id: string) {
  // For the Business Analyst template, try to use the cached version first
  if (type === "sdlc" && id === "ba" && cachedBATemplate) {
    return cachedBATemplate;
  }

  return templateRegistry[type]?.[id] || null;
}

export default templateRegistry;
