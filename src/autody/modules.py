"""Bounded management for AutoDy's official optional modules.

Only the first-party Test Center package is accepted.  The package is data,
not executable plugin code: the core owns the route implementation and only
serves the installed module's isolated static assets.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile


MODULE_ID = "autody-test-center"
MODULE_FILENAME = "AutoDy-Test-Center.autody-module.zip"
MODULE_API_VERSION = "1"
MODULE_PUBLISHER = "AutoDy"
_MANIFEST_NAME = "manifest.json"
_MAX_FILE_COUNT = 16
_MAX_ARCHIVE_BYTES = 512 * 1024
_MAX_EXTRACTED_BYTES = 1024 * 1024
_ALLOWED_FILES = {
    _MANIFEST_NAME,
    "backend.py",
    "frontend/index.html",
    "frontend/module.js",
    "frontend/module.css",
    "README.md",
}


class ModulePackageError(ValueError):
    """Raised when an optional module archive is not safe or compatible."""


def _canonical_checksum(files: dict[str, bytes]) -> str:
    digest = sha256()
    for name in sorted(files):
        if name == _MANIFEST_NAME:
            continue
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(files[name]).digest())
    return digest.hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> dict[str, bytes]:
    if sum(item.compress_size for item in archive.infolist()) > _MAX_ARCHIVE_BYTES:
        raise ModulePackageError("模块包过大")
    if len(archive.infolist()) > _MAX_FILE_COUNT:
        raise ModulePackageError("模块包文件数量超限")
    files: dict[str, bytes] = {}
    extracted_size = 0
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if not name or name.endswith("/"):
            continue
        if path.is_absolute() or ".." in path.parts or name not in _ALLOWED_FILES:
            raise ModulePackageError("非法文件路径或未知模块文件")
        if name in files:
            raise ModulePackageError("模块包包含重复文件")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ModulePackageError("模块包不能包含链接文件")
        if info.file_size > _MAX_EXTRACTED_BYTES:
            raise ModulePackageError("模块文件过大")
        extracted_size += info.file_size
        if extracted_size > _MAX_EXTRACTED_BYTES:
            raise ModulePackageError("模块解压后过大")
        files[name] = archive.read(info)
    return files


def _read_manifest(files: dict[str, bytes], core_version: str) -> dict:
    if set(files) != _ALLOWED_FILES:
        raise ModulePackageError("模块包文件结构不完整或包含未知文件")
    try:
        manifest = json.loads(files[_MANIFEST_NAME].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModulePackageError("模块清单无效") from exc
    expected = {
        "module_id": MODULE_ID,
        "display_name": "测试中心",
        "publisher": MODULE_PUBLISHER,
        "required_autody_version": core_version,
        "module_api_version": MODULE_API_VERSION,
        "backend_entry": "backend.py",
        "frontend_entry": "frontend/index.html",
        "data_directory": "data",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            label = "发布者" if key == "publisher" else "模块标识" if key == "module_id" else "兼容性"
            raise ModulePackageError(f"{label}不匹配")
    if manifest.get("module_version") != "1.0.0":
        raise ModulePackageError("模块版本无效")
    if not isinstance(manifest.get("permissions"), list):
        raise ModulePackageError("模块权限声明无效")
    checksums = manifest.get("file_checksums")
    if not isinstance(checksums, dict) or set(checksums) != _ALLOWED_FILES - {_MANIFEST_NAME}:
        raise ModulePackageError("模块文件校验清单无效")
    if any(checksums.get(name) != sha256(files[name]).hexdigest() for name in checksums):
        raise ModulePackageError("模块文件校验失败")
    if manifest.get("package_checksum") != _canonical_checksum(files):
        raise ModulePackageError("模块包校验失败")
    return manifest


def build_module_archive(destination: Path, *, version: str, mutate: str | None = None) -> Path:
    """Build the official first-party package used by release and tests."""
    payload = {
        "backend.py": b"# Routes are registered by the bounded AutoDy host.\n",
        "frontend/index.html": b"<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><link rel=\"stylesheet\" href=\"module.css\"></head><body><main id=\"root\"></main><script src=\"module.js\"></script></body></html>",
        "frontend/module.js": """const api='/api/modules/autody-test-center';const root=document.getElementById('root');const warning='卸载测试中心后，所有测试历史、测试设置和测试目标覆盖将被永久删除。AutoDy 的正常好友、文案、发送记录和浏览器数据不会受到影响。';const card=(title,body,action='')=>`<section class="card"><h2>${title}</h2><div>${body}</div>${action}</section>`;async function get(path,fallback){try{const r=await fetch(api+path);return r.ok?await r.json():fallback}catch{return fallback}}async function load(){const[plan,failed,pre,status]=await Promise.all([get('/today-plan',{targets:[]}),get('/failed-targets',{items:[]}),get('/preflight/status',{result:null,running:false,progress:null}),get('/diagnostics',{})]);root.innerHTML=`<header><h1>测试中心</h1><p>可选的隔离测试工具；不会输入、粘贴或发送消息。</p></header>${card('发送前自检',pre.result?`最近结果：${pre.result.global_status}`:'暂无预检记录',`<button id="all">检测全部目标</button><button id="one">检测单个目标</button><button id="cancel">取消运行</button>`)}${card('当前进度',pre.running?'正在执行只读预检…':pre.progress?.current_status||'当前没有运行中的测试')}${card('今日异常目标',failed.items?.length?failed.items.map(x=>`<article><b>${x.display_name}</b><small>${x.explanation}</small></article>`).join(''):'今日无异常目标')}${card('今日发送计划',plan.targets?.length?plan.targets.map(x=>`<article><b>${x.display_name}</b><small>${x.planned_at} · ${x.status}</small></article>`).join(''):'今日没有待发送计划')}${card('单目标高级设置','仅保存模块专属的文案包、后缀、顺序和延迟覆盖。')}${card('运行环境',status.environment||'登录、Chromium、浏览器锁和计划任务状态可在此查看。')}${card('安全测试工具','仅允许只读预检和本地夹具。')}${card('受控失败模拟','仅用于模块夹具；不会调用真实发送。')}${card('测试历史',status.history||'暂无模块测试历史')}${card('启动器诊断',status.launcher||'暂无启动器诊断')}${card('环境诊断',status.environment||'暂无环境诊断')}${card('模块管理',warning,'<button class="danger" id="remove">移除测试中心</button>')}`;document.getElementById('all').onclick=()=>fetch(api+'/preflight/run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"target_ids":null}'}).then(load);document.getElementById('one').onclick=()=>alert('请在单目标高级设置中选择目标后执行只读预检。');document.getElementById('cancel').onclick=()=>fetch(api+'/preflight/cancel',{method:'POST'});document.getElementById('remove').onclick=async()=>{if(confirm(warning)){await fetch(api+'/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"confirmed":true}'});parent.postMessage({type:'autody-test-center-removed'},'*')}}}load();
""".encode("utf-8"),
        "frontend/module.css": b"*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#17263d;font:14px system-ui,sans-serif}main{max-width:920px;margin:auto;padding:20px}header{margin-bottom:16px}h1{margin:0}h2{font-size:16px;margin:0 0 10px}.card{background:#fff;border:1px solid #dbe5f0;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 2px 8px #0b244010}article{padding:8px 0;border-top:1px solid #edf1f6}small{display:block;color:#60718a;margin-top:4px}button{border:0;border-radius:8px;padding:8px 12px;margin:8px 6px 0 0;background:#2967c9;color:white}.danger{background:#a94442}\n",
        "README.md": b"# AutoDy Test Center\n",
    }
    # Keep the module frontend self-contained: it runs inside the installed
    # iframe and never contributes styles or scripts to the core application.
    payload["frontend/module.js"] = """const api='/api/modules/autody-test-center';
const root=document.getElementById('root');
const warning='卸载测试中心后，所有测试历史、测试设置和测试目标覆盖将被永久删除。AutoDy 的正常好友、文案、发送记录和浏览器数据不会受到影响。';
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const card=(title,body,action='')=>`<section class="card"><h2>${title}</h2><div>${body}</div>${action}</section>`;
async function get(path,fallback){try{const response=await fetch(api+path);return response.ok?await response.json():fallback}catch{return fallback}}
async function post(path,payload={}){const response=await fetch(api+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!response.ok)throw new Error('请求未完成');return response.json()}
function targetOptions(targets){return targets.map(target=>`<option value="${escapeHtml(target.target_id)}">${escapeHtml(target.display_name)}</option>`).join('')}
async function load(){const[plan,failed,pre,status]=await Promise.all([get('/today-plan',{targets:[]}),get('/failed-targets',{items:[]}),get('/preflight/status',{result:null,running:false,progress:null}),get('/diagnostics',{})]);const targets=plan.targets||[];const progress=pre.running?`正在执行只读预检：${pre.progress?.completed_targets||0}/${pre.progress?.total_targets||0}`:(pre.progress?.current_status||'当前没有运行中的测试');const recent=pre.result?`最近结果：${escapeHtml(pre.result.global_status||'已完成')}`:'暂无预检记录';const failedRows=failed.items?.length?failed.items.map(item=>`<article><b>${escapeHtml(item.display_name)}</b><small>${escapeHtml(item.explanation||item.reason_code||'需要关注')}</small></article>`).join(''):'今日无异常目标';const planRows=targets.length?targets.map(item=>`<article><b>${escapeHtml(item.display_name)}</b><small>${escapeHtml(item.planned_at||'待安排')} · ${escapeHtml(item.status||'待执行')}</small></article>`).join(''):'今日没有待发送计划';const oneAction=targets.length?`<label class="field">选择目标<select id="one-target">${targetOptions(targets)}</select></label><button id="one">检测单个目标</button>`:'<small>没有可检测的已启用目标。</small>';root.innerHTML=`<header><h1>测试中心</h1><p>可选的隔离测试工具；不会输入、粘贴或发送消息。</p></header>${card('发送前自检',recent,`<button id="all">检测全部目标</button>${oneAction}<button id="cancel">取消运行</button><p id="action-status" class="hint" aria-live="polite"></p>`)}${card('当前进度',progress)}${card('今日异常目标',failedRows)}${card('今日发送计划',planRows)}${card('单目标高级设置','模块专属设置当前为空；未保存任何目标覆盖。')}${card('运行环境',escapeHtml(status.environment||'登录、Chromium、浏览器锁和计划任务状态可在此查看。'))}${card('安全测试工具','仅允许只读预检和本地夹具。')}${card('受控失败模拟','当前没有启用的夹具或故障模拟。')}${card('测试历史',escapeHtml(status.history||'暂无模块测试历史'))}${card('启动器诊断',escapeHtml(status.launcher||'暂无启动器诊断'))}${card('环境诊断',escapeHtml(status.environment||'暂无环境诊断'))}${card('模块管理',`<p>${warning}</p><button class="danger" id="remove">移除测试中心</button>`)}<div class="modal" id="remove-dialog" role="dialog" aria-modal="true" aria-labelledby="remove-dialog-title" hidden><div class="modal-card"><h2 id="remove-dialog-title">确认移除测试中心</h2><p>${warning}</p><button id="remove-cancel">取消</button><button class="danger" id="remove-confirm">移除测试中心</button></div></div>`;const statusLine=document.getElementById('action-status');const run=async targetIds=>{try{await post('/preflight/run',{target_ids:targetIds});statusLine.textContent='已登记只读预检请求；不会发送消息。';await load()}catch{statusLine.textContent='预检请求未完成，请稍后重试。'}};document.getElementById('all').onclick=()=>run(null);const one=document.getElementById('one');if(one)one.onclick=()=>run([document.getElementById('one-target').value]);document.getElementById('cancel').onclick=async()=>{await post('/preflight/cancel');statusLine.textContent='已请求取消只读预检。'};const dialog=document.getElementById('remove-dialog');document.getElementById('remove').onclick=()=>{dialog.hidden=false};document.getElementById('remove-cancel').onclick=()=>{dialog.hidden=true};document.getElementById('remove-confirm').onclick=async()=>{const confirm=document.getElementById('remove-confirm');confirm.disabled=true;try{await post('/uninstall',{confirmed:true});parent.postMessage({type:'autody-test-center-removed'},'*')}catch{confirm.disabled=false;dialog.hidden=true;}}}
load();
""".encode("utf-8")
    payload["frontend/module.css"] = b"*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#17263d;font:14px system-ui,sans-serif}main{max-width:920px;margin:auto;padding:20px}header{margin-bottom:16px}h1{margin:0}h2{font-size:16px;margin:0 0 10px}.card{background:#fff;border:1px solid #dbe5f0;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 2px 8px #0b244010}article{padding:8px 0;border-top:1px solid #edf1f6}small,.hint{display:block;color:#60718a;margin-top:4px}.field{display:block;margin-top:8px}select{display:block;max-width:360px;margin-top:5px;padding:7px;border:1px solid #b9c7d8;border-radius:8px}button{border:0;border-radius:8px;padding:8px 12px;margin:8px 6px 0 0;background:#2967c9;color:white}.danger{background:#a94442}.modal[hidden]{display:none}.modal{position:fixed;inset:0;display:grid;place-items:center;padding:20px;background:#17263d88}.modal-card{max-width:520px;background:#fff;border-radius:12px;padding:20px;box-shadow:0 12px 36px #17263d66}\n"
    manifest = {
        "module_id": MODULE_ID,
        "display_name": "测试中心",
        "module_version": version,
        "publisher": MODULE_PUBLISHER,
        "required_autody_version": "1.2.0",
        "module_api_version": MODULE_API_VERSION,
        "backend_entry": "backend.py",
        "frontend_entry": "frontend/index.html",
        "permissions": ["read_core_status", "read_core_state", "manage_module_overrides", "run_safe_diagnostics"],
        "data_directory": "data",
    }
    manifest["file_checksums"] = {name: sha256(data).hexdigest() for name, data in payload.items()}
    all_files = {**payload, _MANIFEST_NAME: b""}
    manifest["package_checksum"] = _canonical_checksum(all_files | {_MANIFEST_NAME: json.dumps(manifest, ensure_ascii=False).encode("utf-8")})
    if mutate == "publisher":
        manifest["publisher"] = "Unknown"
    if mutate == "checksum":
        manifest["package_checksum"] = "0" * 64
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(name, data)
        archive.writestr(_MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        if mutate == "traversal":
            archive.writestr("../escape.txt", "invalid")
    return destination


class ModuleManager:
    def __init__(self, state_root: Path, *, core_version: str):
        self.state_root = state_root.resolve()
        self.core_version = core_version

    @property
    def modules_root(self) -> Path:
        return self.state_root / "modules"

    @property
    def module_root(self) -> Path:
        return self.modules_root / MODULE_ID

    @property
    def registry_path(self) -> Path:
        return self.modules_root / "registry.json"

    def _registry(self) -> dict:
        try:
            value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"modules": {}}
        return value if isinstance(value, dict) and isinstance(value.get("modules"), dict) else {"modules": {}}

    def _write_registry(self, value: dict) -> None:
        self.modules_root.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.registry_path)

    def _safe_module_root(self) -> Path:
        root = self.module_root
        if not str(root) or root.name != MODULE_ID or root.parent != self.modules_root:
            raise ModulePackageError("模块目录不安全")
        resolved_modules = self.modules_root.resolve()
        resolved_root = root.resolve(strict=False)
        try:
            resolved_root.relative_to(resolved_modules)
        except ValueError as exc:
            raise ModulePackageError("模块目录不安全") from exc
        if resolved_root.name != MODULE_ID:
            raise ModulePackageError("模块目录不安全")
        return root

    def status(self) -> dict:
        entry = self._registry()["modules"].get(MODULE_ID)
        installed = bool(entry and self.module_root.is_dir() and (self.module_root / _MANIFEST_NAME).is_file())
        return {
            "id": MODULE_ID,
            "display_name": "测试中心",
            "installed": installed,
            "version": entry.get("version") if installed else None,
            "compatible": True,
            "load_error": None if installed or entry is None else "模块加载失败",
        }

    def installed(self) -> bool:
        return bool(self.status()["installed"])

    def install(self, archive_path: Path) -> dict:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                files = _safe_members(archive)
        except (OSError, zipfile.BadZipFile) as exc:
            raise ModulePackageError("模块包无法读取") from exc
        manifest = _read_manifest(files, self.core_version)
        self.modules_root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{MODULE_ID}-", dir=self.modules_root))
        replacement = temporary / MODULE_ID
        backup = self.modules_root / f".{MODULE_ID}.previous"
        previous_registry = self._registry()
        try:
            replacement.mkdir()
            for name, content in files.items():
                target = replacement / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            (replacement / "data").mkdir()
            if backup.exists():
                shutil.rmtree(backup)
            root = self._safe_module_root()
            if root.exists():
                os.replace(root, backup)
            os.replace(replacement, root)
            registry = json.loads(json.dumps(previous_registry))
            registry["modules"][MODULE_ID] = {"version": manifest["module_version"]}
            self._write_registry(registry)
        except Exception:
            if self.module_root.exists() and backup.exists():
                shutil.rmtree(self.module_root)
                os.replace(backup, self.module_root)
            self._write_registry(previous_registry)
            raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
        return self.status()

    def uninstall(self) -> bool:
        root = self._safe_module_root()
        existed = root.exists()
        if existed:
            shutil.rmtree(root)
        registry = self._registry()
        registry["modules"].pop(MODULE_ID, None)
        if registry["modules"] or self.registry_path.exists():
            self._write_registry(registry)
        return existed
