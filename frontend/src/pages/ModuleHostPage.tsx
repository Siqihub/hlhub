import { useEffect } from "react";

export function ModuleHostPage({ onRemoved }: { onRemoved: () => void }) {
  useEffect(() => {
    const listener = (event: MessageEvent) => { if (event.data?.type === "autody-test-center-removed") onRemoved(); };
    window.addEventListener("message", listener);
    return () => window.removeEventListener("message", listener);
  }, [onRemoved]);
  return <section className="editor-page"><header className="page-header"><div><h1>设置 / 测试中心</h1><p>可选模块，所有测试、预检和诊断均与普通界面隔离。</p></div></header><iframe title="测试中心" className="module-host" src="/api/modules/autody-test-center/frontend/index.html" /></section>;
}
