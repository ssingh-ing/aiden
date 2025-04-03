import "@xyflow/react/dist/style.css";
import { Suspense, useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { LoadingPage } from "./pages/LoadingPage";
import router from "./routes";
import { useDarkStore } from "./stores/darkStore";
import { initializeTemplates } from "./data";

export default function App() {
  const dark = useDarkStore((state) => state.dark);
  const setDark = useDarkStore((state) => state.setDark);

  useEffect(() => {
    // Force dark theme for Ignis style
    if (!dark) {
      setDark(true);
    }

    document.getElementById("body")!.classList.add("dark");
    // Set background color to match Ignis dark theme
    document.body.style.backgroundColor = "#0f0f14";
  }, [dark, setDark]);

  // Initialize templates when the app loads
  useEffect(() => {
    initializeTemplates()
      .then(() => console.log("Global templates initialized"))
      .catch(err => console.error("Failed to initialize global templates:", err));
  }, []);

  return (
    <Suspense fallback={<LoadingPage />}>
      <RouterProvider router={router} />
    </Suspense>
  );
}
