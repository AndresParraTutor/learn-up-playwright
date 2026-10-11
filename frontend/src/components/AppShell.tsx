import { Outlet } from "react-router-dom";
import TopBar from "./TopBar";

export default function AppShell() {
  return (
    <>
      <TopBar />
      <Outlet />
    </>
  );
}
