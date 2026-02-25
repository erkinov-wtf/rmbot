import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

export function AppToaster() {
  return (
    <ToastContainer
      newestOnTop
      limit={6}
      pauseOnFocusLoss={false}
      toastClassName="rm-toast"
      progressClassName="rm-toast-progress"
    />
  );
}
