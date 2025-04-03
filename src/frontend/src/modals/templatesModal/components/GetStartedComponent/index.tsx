import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { cn } from "@/utils/utils";
import { useParams } from "react-router-dom";
import { getTemplateByTypeAndId, initializeTemplates } from "@/data";
import { useEffect } from "react";

// Category definitions
const categories = [
  {
    id: "general",
    name: "General",
    icon: "Layers",
    iconColor: "text-blue-500"
  },
  {
    id: "sdlc",
    name: "SDLC",
    icon: "GitPullRequestDraft",
    iconColor: "text-green-500"
  }
];

// Template definitions
const templatesByCategory = {
  // General Templates
  general: [
    {
      title: "AI Assistant",
      description: "Build a custom AI assistant with memory",
      icon: "BotMessageSquare",
      color: "from-purple-400 to-violet-600",
      type: "chatbots"
    },
    {
      title: "Chat with PDF",
      description: "Create a chat interface to query your PDF documents",
      icon: "FileText",
      color: "from-blue-400 to-blue-600",
      type: "starter"
    },
    {
      title: "Document Q&A",
      description: "Answer questions about uploaded documents",
      icon: "Search",
      color: "from-emerald-400 to-green-600",
      type: "rag"
    },
    {
      title: "Web Research",
      description: "Search and summarize web content",
      icon: "Globe",
      color: "from-cyan-400 to-blue-500",
      type: "web-scraping"
    },
    {
      title: "Content Generator",
      description: "Create marketing content with AI",
      icon: "Newspaper",
      color: "from-rose-400 to-red-600",
      type: "content-generation"
    }
  ],

  // SDLC Templates
  sdlc: [
    {
      title: "Business Analyst",
      description: "AI assistant for gathering and analyzing requirements",
      icon: "ClipboardList",
      color: "from-blue-500 to-indigo-600",
      type: "sdlc-ba"
    },
    {
      title: "Architect",
      description: "Design system architecture and technical specifications",
      icon: "Network",
      color: "from-indigo-400 to-blue-700",
      type: "sdlc-architect"
    },
    {
      title: "QA Engineer",
      description: "Generate test cases and validate software quality",
      icon: "CheckCircle",
      color: "from-green-400 to-emerald-600",
      type: "sdlc-qa"
    },
    {
      title: "DevOps Engineer",
      description: "Automate deployment and infrastructure setup",
      icon: "Workflow",
      color: "from-orange-400 to-red-600",
      type: "sdlc-devops"
    },
    {
      title: "Product Manager",
      description: "Plan and track project timelines and deliverables",
      icon: "Kanban",
      color: "from-purple-400 to-fuchsia-600",
      type: "sdlc-pm"
    },
    {
      title: "Full SDLC Team",
      description: "Comprehensive team of agents for complete development lifecycle",
      icon: "Users",
      color: "from-sky-400 to-cyan-600",
      type: "sdlc-team"
    }
  ]
};

// Template Card Component
const TemplateCard = ({ template, onClick }) => (
  <div
    className="relative overflow-hidden rounded-lg border p-4 transition-all hover:border-primary hover:shadow-md cursor-pointer group"
    onClick={onClick}
  >
    <div className={cn(
      "absolute top-0 left-0 h-full w-1 bg-gradient-to-b",
      template.color
    )} />

    <div className="flex flex-col gap-2">
      <div className={cn(
        "rounded-full h-10 w-10 flex items-center justify-center bg-gradient-to-br",
        template.color
      )}>
        <ForwardedIconComponent name={template.icon} className="h-5 w-5 text-white" />
      </div>

      <div>
        <h4 className="font-semibold group-hover:text-primary">{template.title}</h4>
        <p className="text-sm text-muted-foreground">{template.description}</p>
      </div>

      <div className="mt-2 flex items-center text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
        <span className="flex items-center">
          <ForwardedIconComponent name="ArrowRight" className="h-3 w-3 mr-1" />
          Use template
        </span>
      </div>
    </div>
  </div>
);

// Category Tab Content Component
const CategoryTabContent = ({ category, templates, addFlow, navigate, folderId }) => {
  // Initialize templates when the SDLC category is displayed
  useEffect(() => {
    if (category.id === "sdlc") {
      initializeTemplates()
        .then(() => console.log("Templates initialized for SDLC category"))
        .catch(err => console.error("Failed to initialize templates:", err));
    }
  }, [category.id]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map((template, index) => (
          <TemplateCard
            key={index}
            template={template}
            onClick={() => {
              // For SDLC templates, use the predefined flow templates
              if (category.id === "sdlc") {
                const templateType = template.type.replace("sdlc-", "");
                const predefinedTemplate = getTemplateByTypeAndId("sdlc", templateType);
                if (predefinedTemplate) {
                  // Use the predefined template instead of creating a blank flow
                  addFlow({ flow: predefinedTemplate }).then((id) => {
                    navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
                    track("New Flow Created", {
                      template: template.title,
                      category: category.name,
                      templateType: "predefined"
                    });
                  });
                  return;
                }
              }

              // For general templates
              if (category.id === "general") {
                const templateType = template.type;
                const predefinedTemplate = getTemplateByTypeAndId("general", templateType);
                if (predefinedTemplate) {
                  addFlow({ flow: predefinedTemplate }).then((id) => {
                    navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
                    track("New Flow Created", {
                      template: template.title,
                      category: category.name,
                      templateType: "predefined"
                    });
                  });
                  return;
                }
              }

              // Default behavior if no predefined template is found
              addFlow().then((id) => {
                navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
                track("New Flow Created", {
                  template: template.title,
                  category: category.name
                });
              });
            }}
          />
        ))}
      </div>
    </div>
  );
};

export const GetStartedComponent = () => {
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="text-2xl font-bold">Template Library</div>
        <p className="text-muted-foreground">
          Select a template to accelerate your workflow
        </p>
      </div>

      <Tabs defaultValue="general" className="w-full">
        <TabsList className="mb-4 grid grid-cols-2 w-full max-w-md">
          {categories.map(category => (
            <TabsTrigger key={category.id} value={category.id} className="flex items-center gap-2">
              <ForwardedIconComponent name={category.icon} className={`h-4 w-4 ${category.iconColor}`} />
              {category.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {categories.map(category => (
          <TabsContent key={category.id} value={category.id} className="mt-2">
            <CategoryTabContent
              category={category}
              templates={templatesByCategory[category.id]}
              addFlow={addFlow}
              navigate={navigate}
              folderId={folderId}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default GetStartedComponent;
