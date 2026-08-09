import { createBrowserRouter } from "react-router";
import HomePage from "./components/HomePage";
import ResultsPage from "./components/ResultsPage";
import DeepAnalysisPage from "./components/DeepAnalysisPage";
import ProcessingPage from "./components/ProcessingPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: HomePage,
  },
  {
    path: "/processing/:sessionId",
    Component: ProcessingPage,
  },
  {
    path: "/results/:sessionId",
    Component: ResultsPage,
  },
  {
    path: "/deep/:sessionId/:aspect",
    Component: DeepAnalysisPage,
  },
]);
