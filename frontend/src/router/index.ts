import { createRouter, createWebHistory } from "vue-router";

const HomePage = () => import("../pages/HomePage.vue");
const ChatSandboxPage = () => import("../pages/ChatSandboxPage.vue");
const ConfigEditorPage = () => import("../pages/ConfigEditorPage.vue");
const LogsPage = () => import("../pages/LogsPage.vue");
const MonitoringPage = () => import("../pages/MonitoringPage.vue");
const DbManagementPage = () => import("../pages/DbManagementPage.vue");
const DiagnosisPage = () => import("../pages/DiagnosisPage.vue");
const AdapterConsolePage = () => import("../pages/AdapterConsolePage.vue");
const AdapterLogsPage = () => import("../pages/AdapterLogsPage.vue");
const SecurityInitPage = () => import("../pages/SecurityInitPage.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomePage
    },
    {
      path: "/chat-sandbox",
      name: "chat-sandbox",
      component: ChatSandboxPage
    },
    {
      path: "/config-editor",
      name: "config-editor",
      component: ConfigEditorPage
    },
    {
      path: "/logs",
      name: "logs",
      component: LogsPage
    },
    {
      path: "/monitoring",
      name: "monitoring",
      component: MonitoringPage
    },
    {
      path: "/db-management",
      name: "db-management",
      component: DbManagementPage
    },
    {
      path: "/diagnosis",
      name: "diagnosis",
      component: DiagnosisPage
    },
    {
      path: "/adapter-console",
      name: "adapter-console",
      component: AdapterConsolePage
    },
    {
      path: "/adapter-logs",
      name: "adapter-logs",
      component: AdapterLogsPage
    },
    {
      path: "/security-init",
      name: "security-init",
      component: SecurityInitPage
    }
  ]
});

export default router;
