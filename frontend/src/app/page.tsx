"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { api, AuthUser, fileToBase64, setAuthToken, setUnauthorizedHandler } from "@/lib/api";

type BodyMode = "html" | "text";
type FooterMode = "text" | "image" | "none";
type BottomTab = "list" | "stats" | "logs" | "admin";

const SAMPLE = {
  회사명: "샘플기업",
  대표자명: "홍길동",
  산업분류: "제조업",
  AI_판정: "A",
  이메일: "sample@example.com",
};

// 템플릿 드롭다운의 첫 항목: 아무 템플릿도 적용하지 않고 직접 쓰는 상태
const NO_TMPL = "직접 작성";

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M12 5v14M5 12h14" />
  </svg>
);
const PencilIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></svg>
);
const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6" />
  </svg>
);

function AlignPicker({
  value,
  onChange,
}: {
  value: "왼쪽" | "가운데" | "오른쪽";
  onChange: (v: "왼쪽" | "가운데" | "오른쪽") => void;
}) {
  return (
    <div className="flex gap-1">
      {(["왼쪽", "가운데", "오른쪽"] as const).map((a) => (
        <button
          key={a}
          type="button"
          className={`rounded-md border px-2 py-1 text-xs transition ${
            value === a ? "border-brass bg-brass-50/60 text-ink-900 font-medium" : "border-ink-200 text-ink-500 hover:text-ink-700"
          }`}
          onClick={() => onChange(a)}
        >
          {a}
        </button>
      ))}
    </div>
  );
}

const ChevronDownIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 9l6 6 6-6" />
  </svg>
);

// 변수 태그를 한 줄로 늘어놓는 대신, 클릭하면 열리는 목록에서 골라 커서 위치에 끼워 넣는 메뉴
function VarMenu({
  tags,
  onPick,
}: {
  tags: { label: string; tag: string; disabled?: boolean; hint?: string }[];
  onPick: (tag: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!tags.length) return null;

  return (
    <div className="relative inline-block" ref={boxRef}>
      <button type="button" className="var-menu-btn" onClick={() => setOpen((v) => !v)}>
        변수 넣기
        <ChevronDownIcon />
      </button>
      {open && (
        <div className="var-menu-panel" role="menu">
          {tags.map((v) => (
            <button
              key={v.tag}
              type="button"
              className="var-menu-item"
              role="menuitem"
              disabled={v.disabled}
              title={v.disabled ? v.hint : undefined}
              onClick={() => {
                if (v.disabled) return;
                onPick(v.tag);
                setOpen(false);
              }}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// 아직 안 보냈거나 실패한 수신자만 기본 선택
function pickSelectable(items: any[], st: Record<string, any>): Set<string> {
  return new Set(
    items
      .filter((r) => {
        const log = st[String(r.recipient_id)];
        return !log || log.status === "failed";
      })
      .map((r) => String(r.recipient_id))
  );
}


function RichTextEditor({
  value,
  onChange,
  placeholder,
  editorRef,
  ariaLabel = "서식 입력창",
  toolbarExtra,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  editorRef: React.RefObject<HTMLDivElement | null>;
  ariaLabel?: string;
  toolbarExtra?: React.ReactNode;
}) {
  const lastExternalValue = useRef(value);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) return;
    if (document.activeElement !== el && lastExternalValue.current !== value) {
      el.innerHTML = value || "";
    }
    lastExternalValue.current = value;
  }, [value, editorRef]);

  useEffect(() => {
    const el = editorRef.current;
    if (el && el.innerHTML !== value) el.innerHTML = value || "";
  }, []);

  function command(name: string, arg?: string) {
    editorRef.current?.focus();
    document.execCommand(name, false, arg);
    const html = editorRef.current?.innerHTML || "";
    lastExternalValue.current = html;
    onChange(html);
  }

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-1 rounded-md border border-ink-200 bg-ink-50 px-1.5 py-1">
        <button type="button" className="btn-ghost !px-2 !py-1 text-xs font-bold" title="굵게" aria-label="굵게" onMouseDown={(e) => { e.preventDefault(); command("bold"); }}>B</button>
        <button type="button" className="btn-ghost !px-2 !py-1 text-xs italic" title="이탤릭" aria-label="이탤릭" onMouseDown={(e) => { e.preventDefault(); command("italic"); }}>I</button>
        <button type="button" className="btn-ghost !px-2 !py-1 text-xs underline" title="밑줄" aria-label="밑줄" onMouseDown={(e) => { e.preventDefault(); command("underline"); }}>U</button>
        <span className="mx-1 h-5 w-px bg-ink-200" />
        <button type="button" className="btn-ghost !px-2 !py-1 text-xs" title="글자 크게" aria-label="글자 크게" onMouseDown={(e) => { e.preventDefault(); command("fontSize", "5"); }}>A+</button>
        <button type="button" className="btn-ghost !px-2 !py-1 text-xs" title="글자 작게" aria-label="글자 작게" onMouseDown={(e) => { e.preventDefault(); command("fontSize", "3"); }}>A−</button>
        {toolbarExtra}
      </div>
      <div
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-label={ariaLabel}
        data-placeholder={placeholder || ""}
        className="input min-h-[390px] max-h-[390px] overflow-y-auto overflow-x-hidden text-lg leading-7 whitespace-pre-wrap focus:outline-none"
        onInput={(e) => {
          const html = e.currentTarget.innerHTML;
          lastExternalValue.current = html;
          onChange(html);
        }}
      />
    </div>
  );
}

export default function Home() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [password, setPassword] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginName, setLoginName] = useState("");
  const [loginNameHistory, setLoginNameHistory] = useState<string[]>([]);
  const [loginErr, setLoginErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [presets, setPresets] = useState<Record<string, any>>({});
  const [varTags, setVarTags] = useState<{ label: string; tag: string }[]>([]);
  const [topics, setTopics] = useState<any[]>([]);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [newTopic, setNewTopic] = useState("");
  const [templates, setTemplates] = useState<any[]>([]);

  const [subject, setSubject] = useState("");
  const [plainBody, setPlainBody] = useState("");
  const [htmlBody, setHtmlBody] = useState("");
  const [bodyMode, setBodyMode] = useState<BodyMode>("html");
  const [footerMode, setFooterMode] = useState<FooterMode>("text");
  const [footerText, setFooterText] = useState("감사합니다.\n{발신자}");
  const [activeTab, setActiveTab] = useState<"body" | "footer" | "form">("body");
  const [formUrl, setFormUrl] = useState("");
  const [includeForm, setIncludeForm] = useState(false);

  const [bodyImageB64, setBodyImageB64] = useState<string | null>(null);
  const [footerImageB64, setFooterImageB64] = useState<string | null>(null);
  const [imageWidth, setImageWidth] = useState(80);
  const [footerImageWidth, setFooterImageWidth] = useState(60);
  const [imageAlign, setImageAlign] = useState<"왼쪽" | "가운데" | "오른쪽">("가운데");
  const [footerImageAlign, setFooterImageAlign] = useState<"왼쪽" | "가운데" | "오른쪽">("가운데");
  const [useBodyImage, setUseBodyImage] = useState(false);
  const [showBodyImageOptions, setShowBodyImageOptions] = useState(false);
  const [attachments, setAttachments] = useState<
    { filename: string; content_b64: string; content_type: string; size: number }[]
  >([]);

  const [previewHtml, setPreviewHtml] = useState("");
  const [previewSubj, setPreviewSubj] = useState("");
  const [previewMode, setPreviewMode] = useState<"pc" | "mobile">("pc");

  const [recipients, setRecipients] = useState<any[]>([]);
  const [statusMap, setStatusMap] = useState<Record<string, any>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sendResult, setSendResult] = useState("");
  const [saveTmplName, setSaveTmplName] = useState("");
  const [showSave, setShowSave] = useState(false);
  const [activeTmpl, setActiveTmpl] = useState(NO_TMPL);
  const [showNewTopic, setShowNewTopic] = useState(false);
  const [confirmDelTopic, setConfirmDelTopic] = useState(false);
  const [delTmplTarget, setDelTmplTarget] = useState<string | null>(null);
  const [renameTopicOpen, setRenameTopicOpen] = useState(false);
  const [renameTopicName, setRenameTopicName] = useState("");
  const [savedSettings, setSavedSettings] = useState<any[]>([]);
  const [showSettingsManager, setShowSettingsManager] = useState(false);
  const [editingSettingId, setEditingSettingId] = useState<number | null>(null);
  const [archivedTopics, setArchivedTopics] = useState<any[]>([]);
  const [expandedArchivedTopic, setExpandedArchivedTopic] = useState<number | null>(null);
  const [archivedLogs, setArchivedLogs] = useState<Record<string, any[]>>({});
  const [topicMsg, setTopicMsg] = useState("");
  const lastEnteredTopic = useRef<number | null>(null);
  const subjectRef = useRef<HTMLInputElement>(null);
  const htmlEditorRef = useRef<HTMLDivElement>(null);
  const plainEditorRef = useRef<HTMLDivElement>(null);
  const footerEditorRef = useRef<HTMLDivElement>(null);

  const [bottomTab, setBottomTab] = useState<BottomTab>("list");
  const [stats, setStats] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [senders, setSenders] = useState<any[]>([]);
  const [newSender, setNewSender] = useState({ email: "", display_name: "", is_admin: false, is_active: true });

  const loadMeta = useCallback(async () => {
    const m = await api.meta();
    setPresets(m.presets || {});
    setVarTags(m.var_tags || []);
  }, []);

  const refreshTopics = useCallback(async () => {
    const t = await api.topics();
    setTopics(t);
    if (t.length && topicId == null) setTopicId(t[0].id);
  }, [topicId]);

  useEffect(() => {
    loadMeta().catch(console.error);
  }, [loadMeta]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setPassword("");
      setAuthToken(null);
      setLoginErr("세션이 만료되었습니다. 다시 로그인해 주세요.");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshTopics().catch(console.error);
    api
      .getPrefs(user.email)
      .then((p) => {
        if (p.footer_text) setFooterText(p.footer_text);
        if (p.footer_mode === "text" || p.footer_mode === "image" || p.footer_mode === "none") setFooterMode(p.footer_mode);
        if (p.footer_image_b64) {
          setFooterImageB64(p.footer_image_b64);
          if (p.use_footer_image) setFooterMode("image");
        }
        if (p.footer_image_width) setFooterImageWidth(Number(p.footer_image_width) || 60);
        if (p.footer_image_align === "왼쪽" || p.footer_image_align === "가운데" || p.footer_image_align === "오른쪽")
          setFooterImageAlign(p.footer_image_align);
        if (p.body_mode === "html" || p.body_mode === "text") setBodyMode(p.body_mode);
      })
      .catch(() => {});
  }, [user, refreshTopics]);

  useEffect(() => {
    if (!user) return;
    Promise.all([api.settings(), api.archivedTopics()]).then(([a,b]) => { setSavedSettings(a || []); setArchivedTopics(b || []); }).catch(() => {});
  }, [user]);

  // 입력칸이 비어 있으면 회색 예시(기본형)를 보여주고, 미리보기도 그 예시 기준으로 그린다
  const ex = presets["기본형"] || {};

  useEffect(() => {
    if (!user) return;
    const t = setTimeout(() => {
      api
        .preview({
          subject: subject || ex.subject || "",
          plain_body: plainBody || ex.plain_body || "",
          html_body: htmlBody || ex.html_body || "",
          sender_name: user.name,
          body_mode: bodyMode,
          footer_mode: footerMode,
          footer_text: footerText,
          form_url: formUrl,
          include_form: includeForm,
          body_image_b64: useBodyImage ? bodyImageB64 : null,
          footer_image_b64: footerMode === "image" ? footerImageB64 : null,
          image_width_pct: imageWidth,
          image_align: imageAlign,
          footer_image_width_pct: footerImageWidth,
          footer_image_align: footerImageAlign,
          row: SAMPLE,
        })
        .then((r) => {
          setPreviewSubj(r.subject);
          setPreviewHtml(r.html);
        })
        .catch(() => {});
    }, 280);
    return () => clearTimeout(t);
  }, [
    user,
    subject,
    plainBody,
    htmlBody,
    presets,
    bodyMode,
    footerMode,
    footerText,
    formUrl,
    includeForm,
    bodyImageB64,
    footerImageB64,
    useBodyImage,
    imageWidth,
    footerImageWidth,
    imageAlign,
    footerImageAlign,
  ]);

  useEffect(() => {
    if (!user || bottomTab !== "stats") return;
    api.stats().then(setStats).catch(console.error);
  }, [user, bottomTab]);

  useEffect(() => {
    if (!user || !topicId || bottomTab !== "logs") return;
    api.topicLogs(topicId).then(setLogs).catch(console.error);
  }, [user, topicId, bottomTab]);

  async function toggleArchivedTopic(id: number) {
    if (expandedArchivedTopic === id) { setExpandedArchivedTopic(null); return; }
    setExpandedArchivedTopic(id);
    if (!archivedLogs[String(id)]) {
      try {
        const rows = await api.archivedTopicLogs(id);
        setArchivedLogs((p) => ({ ...p, [String(id)]: rows }));
      } catch {}
    }
  }

  useEffect(() => {
    if (!user || !user.is_admin || bottomTab !== "admin") return;
    api.senders().then(setSenders).catch(console.error);
  }, [user, bottomTab]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("loginNameHistory");
      if (raw) setLoginNameHistory(JSON.parse(raw));
    } catch {
      // 무시: 브라우저 저장소를 못 쓰는 환경이면 그냥 자동완성 없이 진행
    }
  }, []);

  function rememberLoginName(name: string) {
    const v = name.trim();
    if (!v) return;
    try {
      const next = [v, ...loginNameHistory.filter((n) => n !== v)].slice(0, 5);
      setLoginNameHistory(next);
      localStorage.setItem("loginNameHistory", JSON.stringify(next));
    } catch {
      // 무시
    }
  }

  async function doLogin() {
    setLoginErr("");
    setBusy(true);
    try {
      const u = await api.login(loginEmail, password, loginName || undefined);
      setAuthToken(u.token); // 이후 요청이 인증되도록 user 설정보다 먼저
      setUser(u);
      rememberLoginName(loginName);
    } catch (e: any) {
      setLoginErr(e.message || "로그인 실패");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    lastEnteredTopic.current = null;
    setUser(null);
    setPassword("");
    setAuthToken(null);
  }

  function applyPreset(name: string) {
    const p = presets[name];
    if (!p) return;
    setSubject(p.subject || "");
    setPlainBody(p.plain_body || "");
    setHtmlBody(p.html_body || "");
    setBodyMode(p.body_mode === "text" ? "text" : "html");
    setActiveTmpl(name);
  }

  // 아무 템플릿도 고르지 않은 '직접 작성' 상태로 되돌린다 (빈 칸 + 회색 예시)
  function clearCompose() {
    setSubject("");
    setPlainBody("");
    setHtmlBody("");
    setActiveTmpl(NO_TMPL);
  }

  async function applyUserTemplate(name: string, tid: number | null = topicId) {
    if (!user || tid == null) return;
    const t = await api.getTemplate(user.email, tid, name);
    setSubject(t.subject || "");
    setPlainBody(t.plain_body || "");
    setHtmlBody(t.html_body || "");
    setBodyMode(t.body_mode === "text" ? "text" : "html");
    setActiveTmpl(`★ ${name}`);
  }

  // 주제에 들어가면: 그 주제의 템플릿 목록을 불러오고, 연결된 기본 템플릿이 있으면 적용, 없으면 빈 상태로
  async function enterTopic(tid: number) {
    if (!user) return;
    setConfirmDelTopic(false);
    setDelTmplTarget(null);
    setShowSave(false);
    setTopicMsg("");
    const list = await api.templates(user.email, tid);
    setTemplates(list);
    const linked: string | null = topics.find((t) => t.id === tid)?.default_preset || null;
    if (linked && presets[linked]) applyPreset(linked);
    else if (linked && list.some((x: any) => x.name === linked)) await applyUserTemplate(linked, tid);
    else clearCompose();
  }

  useEffect(() => {
    if (!user || topicId == null || !topics.length || !Object.keys(presets).length) return;
    if (lastEnteredTopic.current === topicId) return;
    lastEnteredTopic.current = topicId;
    enterTopic(topicId).catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, topicId, topics, presets]);

  // 주제를 바꾸면 이미 불러온 명단의 발송 여부를 그 주제 기준으로 다시 표시한다
  useEffect(() => {
    if (!user || topicId == null || !recipients.length) return;
    api
      .topicStatus(topicId)
      .then((st) => {
        setStatusMap(st);
        setSelected(pickSelectable(recipients, st));
      })
      .catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, topicId]);

  // 커서가 있던 자리에 변수 태그를 끼워 넣고, 태그 바로 뒤로 커서를 되돌린다
  function insertTag(field: "subject" | "plain" | "html" | "footer", tag: string) {
    function applyAt(el: HTMLInputElement | HTMLTextAreaElement | null, value: string, setValue: (v: string) => void) {
      if (!el) {
        setValue(value + tag);
        return;
      }
      const start = el.selectionStart ?? value.length;
      const end = el.selectionEnd ?? value.length;
      setValue(value.slice(0, start) + tag + value.slice(end));
      const pos = start + tag.length;
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(pos, pos);
      });
    }
    function applyAtEditor(el: HTMLDivElement | null, setValue: (v: string) => void) {
      if (!el) {
        setValue(tag);
        return;
      }
      el.focus();
      const sel = window.getSelection();
      if (!sel || !sel.rangeCount || !el.contains(sel.anchorNode)) {
        el.appendChild(document.createTextNode(tag));
      } else {
        const range = sel.getRangeAt(0);
        range.deleteContents();
        const node = document.createTextNode(tag);
        range.insertNode(node);
        range.setStartAfter(node);
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);
      }
      setValue(el.innerHTML);
    }
    if (field === "subject") applyAt(subjectRef.current, subject, setSubject);
    if (field === "plain") applyAtEditor(plainEditorRef.current, setPlainBody);
    if (field === "html") applyAtEditor(htmlEditorRef.current, setHtmlBody);
    if (field === "footer") applyAtEditor(footerEditorRef.current, setFooterText);
  }

  async function onBodyImage(file: File | null) {
    if (!file) {
      setBodyImageB64(null);
      return;
    }
    // 이미지는 서버가 본문의 {이미지} 자리(없으면 본문 아래)에 한 번만 넣어 줍니다.
    setBodyImageB64(await fileToBase64(file));
    setUseBodyImage(true);
  }

  async function onFooterImage(file: File | null) {
    if (!file) {
      setFooterImageB64(null);
      return;
    }
    setFooterImageB64(await fileToBase64(file));
  }

  const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
  const MAX_ATTACHMENTS_TOTAL_BYTES = 15 * 1024 * 1024;

  async function onAttachFiles(files: FileList | null) {
    if (!files || !files.length) return;
    const next = [...attachments];
    for (const file of Array.from(files)) {
      if (file.size > MAX_ATTACHMENT_BYTES) {
        alert(`'${file.name}'이(가) 너무 큽니다. 파일당 최대 ${MAX_ATTACHMENT_BYTES / (1024 * 1024)}MB까지 첨부할 수 있어요.`);
        continue;
      }
      const totalSoFar = next.reduce((s, a) => s + a.size, 0);
      if (totalSoFar + file.size > MAX_ATTACHMENTS_TOTAL_BYTES) {
        alert(`첨부파일 총 용량이 ${MAX_ATTACHMENTS_TOTAL_BYTES / (1024 * 1024)}MB를 넘어서 '${file.name}'은(는) 추가하지 못했어요.`);
        continue;
      }
      next.push({
        filename: file.name,
        content_b64: await fileToBase64(file),
        content_type: file.type || "application/octet-stream",
        size: file.size,
      });
    }
    setAttachments(next);
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  function currentSettingData() {
    return { sender_name: user?.name || "", topic_id: topicId, topic_name: topics.find((t) => t.id === topicId)?.name || "",
      subject, plain_body: plainBody, html_body: htmlBody, body_mode: bodyMode, template_name: activeTmpl.startsWith("★ ") ? activeTmpl.slice(2) : "", footer_mode: footerMode, footer_text: footerText,
      footer_image_b64: footerImageB64, footer_image_width: footerImageWidth, footer_image_align: footerImageAlign, use_footer_image: footerMode === "image",
      body_image_b64: bodyImageB64, image_width: imageWidth, image_align: imageAlign, use_body_image: useBodyImage, form_url: formUrl, include_form: includeForm, attachments };
  }

  async function saveMySetting() {
    if (!user) return;
    const topicName = topics.find((t) => t.id === topicId)?.name || "메일";
    const name = topicName + " · " + (subject.trim() || "임시 저장").slice(0, 120);
    try {
      const result = await api.saveSetting({ email: user.email, name, data: currentSettingData(), setting_id: editingSettingId || undefined });
      setEditingSettingId(result.id);
      setSavedSettings(await api.settings());
      setShowSettingsManager(true);
      alert(editingSettingId ? "내 설정을 수정해 저장했습니다." : "현재 메일을 내 설정에 저장했습니다.");
    }
    catch (e: any) { alert(e.message || "내 설정을 저장하지 못했습니다."); }
  }

  async function loadMySetting(id: number) {
    if (!user) return;
    try {
      const row = await api.getSetting(id); const d = row.data || {};
      let tid = Number(d.topic_id) || null;
      if (!topics.find((t) => t.id === tid) && d.topic_name) { const created = await api.createTopic(d.topic_name, user.email); setTopics(await api.topics()); tid = created.id; }
      if (tid) {
        lastEnteredTopic.current = tid;
        setTopicId(tid);
        let restoredTemplates = await api.templates(user.email, tid);
        if (d.template_name) {
          const exists = restoredTemplates.some((t: any) => t.name === d.template_name);
          if (!exists) {
            await api.saveTemplate({ owner_email: user.email, topic_id: tid, name: d.template_name, subject: d.subject || "", body_mode: d.body_mode || "html", plain_body: d.plain_body || "", html_body: d.html_body || "" });
            restoredTemplates = await api.templates(user.email, tid);
          }
        }
        setTemplates(restoredTemplates);
      }
      setSubject(d.subject || ""); setPlainBody(d.plain_body || ""); setHtmlBody(d.html_body || ""); setBodyMode((d.body_mode as BodyMode) || "html");
      setFooterMode((d.footer_mode as FooterMode) || "text"); setFooterText(d.footer_text || "감사합니다.\n{발신자}"); setFooterImageB64(d.footer_image_b64 || null);
      setFooterImageWidth(Number(d.footer_image_width) || 60); setFooterImageAlign(d.footer_image_align || "가운데"); setBodyImageB64(d.body_image_b64 || null);
      setImageWidth(Number(d.image_width) || 80); setImageAlign(d.image_align || "가운데"); setUseBodyImage(Boolean(d.use_body_image)); setFormUrl(d.form_url || "");
      setIncludeForm(Boolean(d.include_form)); setAttachments(Array.isArray(d.attachments) ? d.attachments : []); setActiveTmpl(d.template_name ? "★ " + d.template_name : NO_TMPL); setEditingSettingId(id); setShowSettingsManager(false);
    } catch (e: any) { alert(e.message || "내 설정을 불러오지 못했습니다."); }
  }

  async function deleteMySetting(id: number) {
    if (!confirm("이 내 설정을 삭제할까요?")) return;
    try { await api.deleteSetting(id); setSavedSettings(await api.settings()); } catch (e: any) { alert(e.message || "내 설정을 삭제하지 못했습니다."); }
  }
  async function addTopic() {
    if (!user || !newTopic.trim()) return;
    setTopicMsg("");
    try {
      const { id } = await api.createTopic(newTopic.trim(), user.email);
      setNewTopic("");
      setShowNewTopic(false);
      const t = await api.topics();
      setTopics(t);
      setTopicId(id); // 주제로 들어가는 처리는 위 effect가 한 번만 한다
    } catch (e: any) {
      setTopicMsg(e.message || "주제를 만들지 못했습니다");
    }
  }

  async function renameCurrentTopic() { if (topicId == null || !renameTopicName.trim()) return; try { await api.renameTopic(topicId, renameTopicName.trim()); setTopics(await api.topics()); setRenameTopicOpen(false); } catch (e: any) { setTopicMsg(e.message || "주제 이름을 수정하지 못했습니다."); } }

  // 주제 삭제는 서버에서 이력이 있으면 보관 처리한다.
  async function requestDeleteTopic() { if (topicId == null) return; setTopicMsg(""); setConfirmDelTopic(true); }

  async function doDeleteTopic() {
    if (topicId == null) return;
    try {
      await api.deleteTopic(topicId);
      setConfirmDelTopic(false);
      const t = await api.topics();
      setTopics(t);
      lastEnteredTopic.current = null;
      setTopicId(t.length ? t[0].id : null);
      if (!t.length) {
        setTemplates([]);
        clearCompose();
      }
    } catch (e: any) {
      setConfirmDelTopic(false);
      setTopicMsg(e.message || "삭제하지 못했습니다");
    }
  }

  async function saveTemplate() {
    if (!user || topicId == null || !saveTmplName.trim()) return;
    const name = saveTmplName.trim();
    try {
      await api.saveTemplate({
        owner_email: user.email,
        topic_id: topicId,
        name,
        subject,
        body_mode: bodyMode,
        plain_body: plainBody,
        html_body: htmlBody,
      });
      setShowSave(false);
      setSaveTmplName("");
      setTemplates(await api.templates(user.email, topicId));
      setActiveTmpl(`★ ${name}`);
    } catch (e: any) {
      alert(e.message || "저장하지 못했습니다");
    }
  }

  async function doDeleteTemplate(name: string) {
    if (!user || topicId == null) return;
    try {
      await api.deleteTemplate(user.email, topicId, name);
      setDelTmplTarget(null);
      setTemplates(await api.templates(user.email, topicId));
      if (activeTmpl === `★ ${name}`) clearCompose();
    } catch (e: any) {
      setDelTmplTarget(null);
      alert(e.message || "삭제하지 못했습니다");
    }
  }

  async function onExcel(file: File) {
    if (!topicId) {
      alert("주제를 먼저 선택하세요");
      return;
    }
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf);
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json<any>(sheet);
    const items = rows.map((r) => ({
      회사명: String(r["회사명"] ?? ""),
      대표자명: String(r["대표자명"] ?? ""),
      이메일: String(r["이메일"] ?? "").trim().toLowerCase(),
      산업분류: String(r["산업분류"] ?? ""),
      AI_판정: String(r["AI_판정"] ?? ""),
    }));
    const { id_map } = await api.upsertRecipients(items);
    const withIds = items
      .filter((i) => id_map[i.이메일])
      .map((i) => ({ ...i, recipient_id: id_map[i.이메일] }));
    setRecipients(withIds);
    const st = await api.topicStatus(topicId);
    setStatusMap(st);
    setSelected(pickSelectable(withIds, st));
    setBottomTab("list");
  }

  async function doSend() {
    if (!user || !topicId) return;
    const pw = password;
    if (!pw) {
      alert("앱 비밀번호가 없습니다. 다시 로그인해 주세요.");
      return;
    }
    const targets = recipients
      .filter((r) => selected.has(String(r.recipient_id)))
      .map((r) => ({
        recipient_id: r.recipient_id,
        이메일: r.이메일,
        회사명: r.회사명,
        대표자명: r.대표자명,
        산업분류: r.산업분류,
        AI_판정: r.AI_판정,
      }));
    if (!targets.length) {
      alert("발송 대상이 없습니다");
      return;
    }
    // 이미 발송 완료된 주소를 다시 선택해서 보내려는 경우, 한 번 더 확인
    const alreadySentCount = targets.filter((t) => {
      const log = statusMap[String(t.recipient_id)] || statusMap[t.recipient_id];
      return log?.status === "sent";
    }).length;
    if (alreadySentCount > 0) {
      const ok = window.confirm(
        `선택한 ${targets.length}건 중 ${alreadySentCount}건은 이 주제로 이미 발송 완료된 주소입니다.\n` +
          "그래도 다시 보낼까요? 같은 사람에게 메일이 한 번 더 갑니다."
      );
      if (!ok) return;
    }
    // 눌렀을 때 바로 확인: 제목/본문이 비어 있으면 보내지 않는다
    const needText = bodyMode === "text";
    const needHtml = bodyMode === "html";
    if (!subject.trim() || (needText && !plainBody.trim()) || (needHtml && !htmlBody.trim())) {
      alert("제목과 본문을 입력해 주세요.");
      return;
    }
    if (includeForm && formUrl.trim() && !/^https?:\/\//i.test(formUrl.trim())) {
      alert("구글 폼 링크는 https:// 로 시작해야 합니다. 설문지 탭에서 확인해 주세요.");
      return;
    }
    // 일일 한도(Gmail 500건): 서버 기준 오늘 발송 수를 다시 가져와 확인
    let allowOver = false;
    try {
      const stt = await api.stats();
      const todayCnt = Number(stt.sent_today?.[user.email] ?? 0);
      setUser((u) => (u ? { ...u, sent_today: todayCnt } : u));
      const limit = user.daily_limit || 500;
      if (todayCnt + targets.length > limit) {
        const ok = window.confirm(
          `오늘 이 계정 발송 ${todayCnt}건 + 이번 ${targets.length}건 = ${todayCnt + targets.length}건으로 일일 한도(${limit}건)를 넘습니다.\n` +
            "Gmail이 중간에 발송을 막을 수 있습니다. 그래도 진행할까요? (Google Workspace 등 한도가 더 큰 계정만)"
        );
        if (!ok) return;
        allowOver = true;
      }
    } catch {
      /* 조회 실패 시 서버가 한 번 더 검사한다 */
    }
    setBusy(true);
    setSendResult("");
    try {
      const r = await api.send({
        topic_id: topicId,
        sender_email: user.email,
        sender_name: user.name,
        sender_password: pw,
        subject,
        plain_body: plainBody,
        html_body: htmlBody,
        body_mode: bodyMode,
        footer_mode: footerMode,
        footer_text: footerText,
        form_url: formUrl,
        include_form: includeForm,
        body_image_b64: useBodyImage ? bodyImageB64 : null,
        footer_image_b64: footerMode === "image" ? footerImageB64 : null,
        image_width_pct: imageWidth,
        image_align: imageAlign,
        footer_image_width_pct: footerImageWidth,
        footer_image_align: footerImageAlign,
        attachments: attachments.map((a) => ({
          filename: a.filename,
          content_b64: a.content_b64,
          content_type: a.content_type,
        })),
        targets,
        delay_sec: 2,
        allow_over_limit: allowOver,
      });
      setSendResult(`성공 ${r.sent} · 건너뜀 ${r.skipped} · 실패 ${r.failed}`);
      if (r.errors?.length) setSendResult((s) => s + "\n" + r.errors.join("\n"));
      setStatusMap(await api.topicStatus(topicId));
      setUser((u) => (u ? { ...u, sent_today: u.sent_today + r.sent } : u));
      if (bottomTab === "logs") setLogs(await api.topicLogs(topicId));
    } catch (e: any) {
      setSendResult(e.message || "발송 오류");
    } finally {
      setBusy(false);
    }
  }

  async function saveSender() {
    if (!newSender.email.trim()) return;
    await api.upsertSender(newSender);
    setNewSender({ email: "", display_name: "", is_admin: false, is_active: true });
    setSenders(await api.senders());
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-5 text-center">
            <div className="inline-block h-[3px] w-10 bg-brass rounded-full mb-3" />
            <h1 className="text-xl font-bold tracking-tight text-ink-900">기업 이메일 발송 시스템</h1>
            <p className="text-sm text-ink-500 mt-1">등록된 Gmail + 앱 비밀번호로 로그인</p>
          </div>
          <div className="card p-6 space-y-3">
            <input className="input" placeholder="Gmail" autoComplete="username" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} />
            <input
              className="input"
              type="password"
              placeholder="앱 비밀번호"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div>
              <input
                className="input"
                placeholder="발신자 이름 (선택)"
                autoComplete="off"
                list="login-name-history"
                value={loginName}
                onChange={(e) => setLoginName(e.target.value)}
              />
              <datalist id="login-name-history">
                {loginNameHistory.map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
            </div>
            {loginErr && <p className="text-sm text-red-600">{loginErr}</p>}
            <button className="btn-primary w-full" disabled={busy} onClick={doLogin}>
              {busy ? "확인 중…" : "로그인"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const presetNames = Object.keys(presets);
  const userTmplNames = templates.map((t) => t.name);
  // '본문에 이미지 추가'을 체크하기 전까지는 {이미지} 변수를 끼워 넣어도 의미가 없으므로 비활성화
  const varTagsForBody = varTags.map((v) =>
    v.tag === "{이미지}" ? { ...v, disabled: !useBodyImage, hint: "먼저 아래 '본문 이미지 사용'을 체크하세요" } : v
  );

  return (
    <div className="min-h-screen pb-10">
      <header className="bg-ink-900 border-b-2 border-brass px-5 py-3.5">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between gap-4">
          <div>
            <h1 className="text-base font-bold text-ink-50 tracking-tight">기업 이메일 발송 시스템</h1>
            <p className="text-xs text-ink-50/60">맞춤 메일 · 중복 발송 방지 · 다중 계정</p>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-right">
              <div className="font-medium text-ink-50">{user.name}</div>
              <div className="text-ink-50/60 text-xs">
                {user.email} · 오늘 {user.sent_today}/{user.daily_limit}
              </div>
            </div>
            <button className="btn-ghost-dark" onClick={logout}>
              로그아웃
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <section className="space-y-3">
          <div className="card p-4 space-y-2">
            <div className="flex items-center gap-2">
              <span className="card-title mb-0 shrink-0 !text-base">테마</span>
              <select
                className="input text-lg"
                aria-label="발송 주제"
                value={topicId ?? ""}
                onChange={(e) => setTopicId(Number(e.target.value))}
              >
                {topics.length === 0 && <option value="">아직 주제가 없습니다. 오른쪽 + 버튼으로 만들어 주세요.</option>}
                {topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-ghost !px-2.5"
                title="새 주제 만들기"
                aria-label="새 주제 만들기"
                onClick={() => {
                  setShowNewTopic((v) => !v);
                  setTopicMsg("");
                }}
              >
                <PlusIcon />
              </button>{topicId != null && <button type="button" className="btn-ghost !px-2.5" title="주제 이름 수정" aria-label="주제 이름 수정" onClick={() => { setRenameTopicName(topics.find((t) => t.id === topicId)?.name || ""); setRenameTopicOpen(true); }}><PencilIcon /></button>}
              {topicId != null && (
                <button
                  type="button"
                  className="btn-ghost !px-2.5"
                  title="이 주제 삭제"
                  aria-label="이 주제 삭제"
                  onClick={requestDeleteTopic}
                >
                  <TrashIcon />
                </button>
              )}
            </div>
            {renameTopicOpen && (
              <div className="flex gap-2">
                <input className="input" aria-label="주제 이름 수정" value={renameTopicName} onChange={(e) => setRenameTopicName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && renameCurrentTopic()} />
                <button type="button" className="btn-primary" onClick={renameCurrentTopic}>저장</button>
                <button type="button" className="btn-ghost" onClick={() => setRenameTopicOpen(false)}>취소</button>
              </div>
            )}
            {showNewTopic && (
              <div className="flex gap-2">
                <input
                  className="input"
                  aria-label="새 주제 이름"
                  placeholder="예: 2026 세제개편 세미나 초청"
                  value={newTopic}
                  onChange={(e) => setNewTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addTopic()}
                />
                <button type="button" className="btn-primary whitespace-nowrap" onClick={addTopic}>
                  확인
                </button>
                <button
                  type="button"
                  className="btn-ghost whitespace-nowrap"
                  onClick={() => {
                    setShowNewTopic(false);
                    setNewTopic("");
                  }}
                >
                  취소
                </button>
              </div>
            )}
            {confirmDelTopic && (
              <div className="flex flex-wrap items-center gap-2 text-sm bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                <span className="flex-1">「{topics.find((t) => t.id === topicId)?.name}」 주제를 삭제할까요? 이 주제의 템플릿도 함께 지워집니다.</span>
                <button type="button" className="btn-primary" onClick={doDeleteTopic}>
                  삭제
                </button>
                <button type="button" className="btn-ghost" onClick={() => setConfirmDelTopic(false)}>
                  취소
                </button>
              </div>
            )}
            {topicMsg && (
              <div role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {topicMsg}
              </div>
            )}
          </div>

          <div className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="card-title mb-0 !text-base">메일 작성</div>
              <div className="flex items-center gap-2">
                <button type="button" className="btn-ghost !py-1.5 !px-2.5 text-xs" title="현재 작성 중인 메일을 임시 저장" onClick={saveMySetting}>임시저장</button>
                <button
                  type="button"
                  className="btn-ghost !py-1.5 !px-2.5 text-xs"
                  title="저장된 메일 설정 불러오기"
                  onClick={async () => {
                    const rows = await api.settings();
                    setSavedSettings(rows || []);
                    setShowSettingsManager(true);
                  }}
                >
                  불러오기
                </button>
              </div>
            </div>
            {showSettingsManager && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowSettingsManager(false); }}>
                <div className="w-full max-w-md rounded-xl bg-white shadow-xl border border-ink-200 p-4 space-y-3" role="dialog" aria-modal="true" aria-label="저장된 메일 설정 불러오기">
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-ink-900">저장된 메일 설정</div>
                    <button type="button" className="btn-ghost !px-2 !py-1 text-sm" onClick={() => setShowSettingsManager(false)} aria-label="닫기">닫기</button>
                  </div>
                  {!savedSettings.length ? (
                    <div className="text-sm text-ink-500 py-4 text-center">저장된 설정이 없습니다.</div>
                  ) : (
                    <div className="max-h-72 overflow-auto space-y-1">
                      {savedSettings.map((st) => (
                        <div key={st.id} className="flex items-center gap-2 rounded-md border border-ink-200 bg-white px-2 py-1.5">
                          <button type="button" className="flex-1 text-left text-sm truncate py-1" onClick={() => loadMySetting(st.id)}>
                            {st.name}
                          </button>
                          <button type="button" className="btn-ghost !px-2 !py-1" title="삭제" onClick={() => deleteMySetting(st.id)} aria-label="삭제">
                            <TrashIcon />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-ink-900 shrink-0">템플릿</span>
              <select
                className="input flex-1 min-w-0"
                aria-label="템플릿 선택"
                value={activeTmpl}
                disabled={topicId == null}
                onChange={(e) => {
                  const v = e.target.value;
                  setDelTmplTarget(null);
                  if (v === NO_TMPL) clearCompose();
                  else if (v.startsWith("★ ")) applyUserTemplate(v.slice(2)).catch(console.error);
                  else applyPreset(v);
                }}
              >
                <option value={NO_TMPL}>{NO_TMPL}</option>
                {presetNames.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
                {userTmplNames.map((n) => (
                  <option key={n} value={`★ ${n}`}>
                    ★ {n}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-ghost !px-2.5"
                title="현재 내용을 새 템플릿으로 저장"
                aria-label="새 템플릿으로 저장"
                disabled={topicId == null}
                onClick={() => {
                  setShowSave((v) => !v);
                  setDelTmplTarget(null);
                }}
              >
                <PlusIcon />
              </button><button type="button" className="btn-ghost !px-2.5" title="선택한 템플릿 수정" aria-label="선택한 템플릿 수정" disabled={!activeTmpl.startsWith("★ ")} onClick={() => { setSaveTmplName(activeTmpl.slice(2)); setShowSave(true); setDelTmplTarget(null); }}><PencilIcon /></button>
              <button
                type="button"
                className="btn-ghost !px-2.5"
                title={activeTmpl.startsWith("★ ") ? "이 템플릿 삭제" : "저장된(★) 템플릿을 선택하면 삭제할 수 있습니다"}
                aria-label="이 템플릿 삭제"
                disabled={!activeTmpl.startsWith("★ ")}
                onClick={() => setDelTmplTarget(activeTmpl.slice(2))}
              >
                <TrashIcon />
              </button>
            </div>

            {showSave && (
              <div className="space-y-2 bg-ink-50 border border-ink-200 rounded-lg px-3 py-2.5">
                <div className="text-sm font-medium text-ink-900">현재 메일을 템플릿으로 저장하기</div>
                <div className="flex gap-2">
                  <input
                    className="input"
                    aria-label="새 템플릿 이름"
                    placeholder="템플릿 이름"
                    value={saveTmplName}
                    onChange={(e) => setSaveTmplName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveTemplate()}
                  />
                  <button type="button" className="btn-primary whitespace-nowrap" onClick={saveTemplate}>
                    확인
                  </button>
                  <button
                    type="button"
                    className="btn-ghost whitespace-nowrap"
                    onClick={() => {
                      setShowSave(false);
                      setSaveTmplName("");
                    }}
                  >
                    취소
                  </button>
                </div>
              </div>
            )}
            {delTmplTarget && (
              <div className="space-y-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 text-sm">
                <div>
                  <div className="font-medium text-ink-900">현재 템플릿을 삭제하기</div>
                  <div className="text-ink-500">「{delTmplTarget}」 · 되돌릴 수 없습니다.</div>
                </div>
                <div className="flex gap-2">
                  <button type="button" className="btn-primary" onClick={() => doDeleteTemplate(delTmplTarget)}>
                    삭제
                  </button>
                  <button type="button" className="btn-ghost" onClick={() => setDelTmplTarget(null)}>
                    취소
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-ink-900 shrink-0">제목</span>
                <div className="relative flex-1 min-w-0">
                  <input ref={subjectRef} className="input pr-24" aria-label="제목" placeholder={ex.subject || "제목"} value={subject} onChange={(e) => setSubject(e.target.value)} />
                  <div className="absolute right-1 top-1/2 -translate-y-1/2">
                    <VarMenu tags={varTagsForBody} onPick={(tag) => insertTag("subject", tag)} />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="doc-tabs flex-1 min-w-0">
                {(["body", "footer", "form"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    className="doc-tab"
                    data-active={activeTab === tab}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab === "body" ? "본문" : tab === "footer" ? "푸터" : "설문지"}
                  </button>
                ))}
              </div>
              {activeTab === "body" && (
                <div className="seg shrink-0">
                  {(
                    [
                      ["html", "HTML"],
                      ["text", "텍스트"],
                    ] as const
                  ).map(([k, label]) => (
                    <button key={k} type="button" data-active={bodyMode === k} onClick={() => setBodyMode(k)}>
                      {label}
                    </button>
                  ))}
                </div>
              )}
              {activeTab === "footer" && (
                <div className="seg shrink-0">
                  {(
                    [
                      ["text", "텍스트"],
                      ["image", "이미지"],
                      ["none", "없음"],
                    ] as const
                  ).map(([k, label]) => (
                    <button key={k} type="button" data-active={footerMode === k} onClick={() => setFooterMode(k)}>
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="h-[445px] overflow-y-auto overflow-x-hidden">
            {activeTab === "body" && (
              <div className="space-y-2">
                {bodyMode === "text" && (
                  <div className="space-y-1">
                    <RichTextEditor
                      value={plainBody}
                      onChange={setPlainBody}
                      placeholder={ex.plain_body}
                      editorRef={plainEditorRef}
                      ariaLabel="텍스트 본문"
                      toolbarExtra={<VarMenu tags={varTagsForBody} onPick={(tag) => insertTag("plain", tag)} />}
                    />
                  </div>
                )}
                {bodyMode === "html" && (
                  <div className="space-y-1">
                    <RichTextEditor
                      value={htmlBody}
                      onChange={setHtmlBody}
                      placeholder={ex.html_body}
                      editorRef={htmlEditorRef}
                      toolbarExtra={<VarMenu tags={varTagsForBody} onPick={(tag) => insertTag("html", tag)} />}
                    />
                  </div>
                )}
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={useBodyImage}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setUseBodyImage(checked);
                      setShowBodyImageOptions(checked);
                    }}
                  />
                  본문에 이미지 추가
                </label>
                {showBodyImageOptions && (
                  <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
                    onMouseDown={(e) => {
                      if (e.target === e.currentTarget) setShowBodyImageOptions(false);
                    }}
                  >
                    <div
                      className="w-full max-w-md rounded-xl bg-white shadow-xl border border-ink-200 p-4 space-y-3"
                      role="dialog"
                      aria-modal="true"
                      aria-label="본문 이미지 설정"
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-medium text-ink-900">본문 이미지 설정</div>
                        <button type="button" className="btn-ghost !px-2 !py-1 text-sm" onClick={() => setShowBodyImageOptions(false)}>닫기</button>
                      </div>
                      <label className="btn-ghost inline-flex cursor-pointer items-center gap-2">
                        이미지 선택
                        <input type="file" accept="image/*" className="hidden" onChange={(e) => onBodyImage(e.target.files?.[0] || null)} />
                      </label>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-ink-500">너비</span>
                        <input
                          type="range"
                          min={20}
                          max={100}
                          step={5}
                          value={imageWidth}
                          onChange={(e) => setImageWidth(Number(e.target.value))}
                        />
                        <span>{imageWidth}%</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-ink-500">위치</span>
                        <AlignPicker value={imageAlign} onChange={setImageAlign} />
                      </div>
                      {bodyImageB64 && (
                        <img src={`data:image/png;base64,${bodyImageB64}`} alt="body" className="max-h-32 rounded border border-ink-200" />
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "footer" && (
              <div className="space-y-2">
                {footerMode === "text" && (
                  <RichTextEditor
                    value={footerText}
                    onChange={setFooterText}
                    placeholder="푸터 문구"
                    editorRef={footerEditorRef}
                    ariaLabel="푸터 문구"
                  />
                )}
                {footerMode === "image" && (
                  <div className="space-y-2">
                    <label className="btn-ghost inline-flex cursor-pointer items-center gap-2">
                      이미지 선택
                      <input type="file" accept="image/*" className="hidden" onChange={(e) => onFooterImage(e.target.files?.[0] || null)} />
                    </label>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-ink-500">너비</span>
                      <input
                        type="range"
                        min={20}
                        max={100}
                        step={5}
                        value={footerImageWidth}
                        onChange={(e) => setFooterImageWidth(Number(e.target.value))}
                      />
                      <span>{footerImageWidth}%</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-ink-500">위치</span>
                      <AlignPicker value={footerImageAlign} onChange={setFooterImageAlign} />
                    </div>
                    {footerImageB64 && (
                      <img
                        src={`data:image/png;base64,${footerImageB64}`}
                        alt="footer"
                        className="max-h-28 rounded border border-ink-200"
                      />
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === "form" && (
              <div className="space-y-2">
                <input
                  className="input"
                  placeholder="Google Forms 링크"
                  value={formUrl}
                  onChange={(e) => setFormUrl(e.target.value)}
                />
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={includeForm} onChange={(e) => setIncludeForm(e.target.checked)} />
                  메일에 설문 버튼 포함
                </label>
                {formUrl.trim() && !/^https?:\/\//i.test(formUrl.trim()) && (
                  <p className="text-xs text-red-600">링크는 https:// 로 시작해야 합니다.</p>
                )}
                {/docs\.google\.com\/forms\/d\/[\w-]+\/edit/i.test(formUrl) && (
                  <p className="text-xs text-ink-500">편집 주소는 받는 사람이 열 수 없어, 발송할 때 응답자용 주소(viewform)로 자동 변환됩니다.</p>
                )}
              </div>
            )}
            </div>

            <div className="space-y-2 pt-2 border-t border-ink-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label className="btn-ghost inline-flex cursor-pointer items-center gap-2 !py-1.5">
                    파일첨부
                    <input type="file" multiple className="hidden" onChange={(e) => onAttachFiles(e.target.files)} />
                  </label>
                  <span className="text-xs text-ink-500">(파일당 최대 10MB)</span>
                </div>
                {attachments.length > 0 && (
                  <span className="text-xs text-ink-500">
                    {attachments.length}개 · {(attachments.reduce((s, a) => s + a.size, 0) / (1024 * 1024)).toFixed(1)}MB
                  </span>
                )}
              </div>
                            {attachments.length > 0 && (
                <ul className="space-y-1">
                  {attachments.map((a, i) => (
                    <li
                      key={`${a.filename}-${i}`}
                      className="flex items-center justify-between gap-2 text-xs bg-ink-50 border border-ink-200 rounded px-2 py-1"
                    >
                      <span className="truncate">
                        {a.filename} · {(a.size / 1024).toFixed(0)}KB
                      </span>
                      <button
                        type="button"
                        className="shrink-0 rounded p-1 text-ink-500 hover:bg-ink-200/70 hover:text-red-700 transition"
                        title="첨부 제거"
                        aria-label={`${a.filename} 첨부 제거`}
                        onClick={() => removeAttachment(i)}
                      >
                        <TrashIcon />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>

        <section className="card p-4 space-y-2 md:flex md:flex-col">
          <div className="flex items-center justify-between shrink-0">
            <div className="card-title">실시간 미리보기</div>
            <div className="seg">
              <button type="button" data-active={previewMode === "pc"} onClick={() => setPreviewMode("pc")}>PC</button>
              <button type="button" data-active={previewMode === "mobile"} onClick={() => setPreviewMode("mobile")}>📱 모바일</button>
            </div>
          </div>
          <div className="text-sm text-ink-700 bg-ink-50 border border-ink-200 rounded-lg px-3 py-2.5 shrink-0">
            <b className="text-base">제목</b>
            <span className="ml-2 text-base font-medium text-ink-900">{previewSubj || "—"}</span>
          </div>
          <div className="bg-ink-100 rounded-lg border border-ink-200 overflow-hidden min-h-[520px] md:flex-1 flex items-start justify-center p-3">
            <iframe
              title={previewMode === "mobile" ? "mobile-preview" : "preview"}
              className={previewMode === "mobile" ? "bg-white h-full w-[375px] max-w-full shadow-sm" : "w-full h-full bg-white"}
              sandbox="allow-popups"
              srcDoc={previewHtml || "<p style='padding:16px;color:#888'>미리보기</p>"}
            />
          </div>
        </section>

        <section className="md:col-span-2">
          <div className="doc-tabs">
            {(
              [
                ["list", "발송 명단"],
                ["stats", "현황"],
                ["logs", "발송 내역"],
                ...(user.is_admin ? ([["admin", "발신 계정"]] as const) : []),
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                className="doc-tab"
                data-active={bottomTab === k}
                onClick={() => setBottomTab(k as BottomTab)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="card rounded-tl-none p-4 space-y-3">
          {bottomTab === "list" && (
            <div className="space-y-3">
              <label className="btn-ghost inline-flex cursor-pointer items-center gap-2">
                불러오기
                <input type="file" accept=".xlsx,.xls" className="hidden" onChange={(e) => e.target.files?.[0] && onExcel(e.target.files[0])} />
              </label>
              {recipients.length > 0 && (
                <>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <button
                      type="button"
                      className="btn-ghost !py-1 !px-2.5"
                      onClick={() => setSelected(new Set(recipients.map((r) => String(r.recipient_id))))}
                    >
                      전체 선택
                    </button>
                    <button type="button" className="btn-ghost !py-1 !px-2.5" onClick={() => setSelected(new Set())}>
                      전체 해제
                    </button>
                    <button
                      type="button"
                      className="btn-ghost !py-1 !px-2.5"
                      onClick={() => setSelected(pickSelectable(recipients, statusMap))}
                    >
                      미발송만 선택
                    </button>
                    <span className="text-ink-500">선택 {selected.size} / 전체 {recipients.length}</span>
                  </div>
                  <div className="scroll-box h-64">
                    <table className="w-full text-sm">
                      <thead className="bg-ink-50 sticky top-0">
                        <tr>
                          <th className="p-2 text-left w-12">선택</th>
                          <th className="p-2 text-left">회사</th>
                          <th className="p-2 text-left">이메일</th>
                          <th className="p-2 text-left">상태</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recipients.map((r) => {
                          const log = statusMap[String(r.recipient_id)] || statusMap[r.recipient_id];
                          const st = log?.status || "none";
                          const label =
                            st === "sent" ? "발송완료" : st === "failed" ? "실패" : st === "pending" ? "발송중" : "미발송";
                          const rowBg =
                            st === "sent"
                              ? "bg-emerald-50/60"
                              : st === "failed"
                                ? "bg-red-50/60"
                                : st === "pending"
                                  ? "bg-amber-50/60"
                                  : "";
                          const badge =
                            st === "sent"
                              ? "bg-emerald-100 text-emerald-800"
                              : st === "failed"
                                ? "bg-red-100 text-red-800"
                                : st === "pending"
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-ink-100 text-ink-500";
                          return (
                            <tr key={r.recipient_id} className={`border-t border-ink-100 ${rowBg}`}>
                              <td className="p-2">
                                <input
                                  type="checkbox"
                                  checked={selected.has(String(r.recipient_id))}
                                  onChange={(e) => {
                                    const next = new Set(selected);
                                    if (e.target.checked) next.add(String(r.recipient_id));
                                    else next.delete(String(r.recipient_id));
                                    setSelected(next);
                                  }}
                                />
                              </td>
                              <td className="p-2">{r.회사명}</td>
                              <td className="p-2">{r.이메일}</td>
                              <td className="p-2">
                                <span className={`rounded-full px-2 py-0.5 text-xs ${badge}`}>{label}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <button className="btn-primary" disabled={busy || !selected.size} onClick={doSend}>
                      {busy ? "발송 중…" : `선택 ${selected.size}건 발송`}
                    </button>
                    {sendResult && <pre className="text-xs text-ink-700 whitespace-pre-wrap">{sendResult}</pre>}
                  </div>
                </>
              )}
            </div>
          )}

          {bottomTab === "stats" && (
            <div className="space-y-3 text-sm">
              {!stats ? (
                <p className="text-ink-500">불러오는 중…</p>
              ) : (
                <>
                  <p>
                    DB 수신자 수: <b>{stats.recipients}</b>
                  </p>
                  <div>
                    <div className="font-medium mb-1">오늘 계정별 발송</div>
                    <ul className="list-disc pl-5 text-ink-700">
                      {Object.entries(stats.sent_today || {}).map(([k, v]) => (
                        <li key={k}>
                          {k}: {String(v)}
                        </li>
                      ))}
                      {!Object.keys(stats.sent_today || {}).length && <li>없음</li>}
                    </ul>
                  </div>
                </>
              )}
            </div>
          )}

          {bottomTab === "logs" && (
            <div className="space-y-3">
              <div className="overflow-auto max-h-80 border border-ink-200 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-ink-50 sticky top-0">
                  <tr>
                    <th className="p-2 text-left">시각</th>
                    <th className="p-2 text-left">발신</th>
                    <th className="p-2 text-left">수신</th>
                    <th className="p-2 text-left">상태</th>
                    <th className="p-2 text-left">제목</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((d) => (
                    <tr key={d.id} className="border-t border-ink-100">
                      <td className="p-2 whitespace-nowrap text-xs">{d.sent_at || d.claimed_at || "—"}</td>
                      <td className="p-2">{d.sender_name || d.sender_email}</td>
                      <td className="p-2">{d.recipients?.company || d.recipients?.email}</td>
                      <td className="p-2">{d.status}</td>
                      <td className="p-2 truncate max-w-[200px]">{d.subject}</td>
                    </tr>
                  ))}
                  {!logs.length && (
                    <tr>
                      <td colSpan={5} className="p-4 text-ink-500 text-center">
                        내역 없음 (주제 선택 후 확인)
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
              {archivedTopics.length > 0 && (
                <div className="border border-amber-200 rounded-lg bg-amber-50/50">
                  <button type="button" className="w-full flex items-center justify-between px-3 py-2 text-sm text-left" onClick={() => setExpandedArchivedTopic(expandedArchivedTopic === -1 ? null : -1)}>
                    <span>삭제된 주제의 발송내역 ({archivedTopics.length})</span><ChevronDownIcon />
                  </button>
                  {expandedArchivedTopic === -1 && <div className="p-2 space-y-2 border-t border-amber-200">
                    {archivedTopics.map((t) => <div key={t.id} className="border border-amber-200 rounded-md bg-white">
                      <button type="button" className="w-full flex items-center justify-between px-2 py-2 text-sm text-left" onClick={() => toggleArchivedTopic(t.id)}>
                        <span>{t.name}</span><span className="text-xs text-ink-500">{t.log_count}건</span>
                      </button>
                      {expandedArchivedTopic === t.id && <div className="overflow-auto border-t border-ink-100">
                        <table className="w-full text-xs"><thead className="bg-ink-50"><tr><th className="p-2 text-left">시각</th><th className="p-2 text-left">수신</th><th className="p-2 text-left">상태</th><th className="p-2 text-left">제목</th></tr></thead>
                        <tbody>{(archivedLogs[String(t.id)] || []).map((d) => <tr key={d.id} className="border-t border-ink-100"><td className="p-2">{d.sent_at || d.claimed_at || "—"}</td><td className="p-2">{d.recipients?.company || d.recipients?.email}</td><td className="p-2">{d.status}</td><td className="p-2 truncate max-w-[240px]">{d.subject}</td></tr>)}</tbody></table>
                      </div>}
                    </div>)}
                  </div>}
                </div>
              )}
            </div>
          )}

          {bottomTab === "admin" && user.is_admin && (
            <div className="space-y-3">
              <div className="overflow-auto max-h-48 border border-ink-200 rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-ink-50">
                    <tr>
                      <th className="p-2 text-left">이메일</th>
                      <th className="p-2 text-left">이름</th>
                      <th className="p-2 text-left">관리자</th>
                      <th className="p-2 text-left">활성</th>
                    </tr>
                  </thead>
                  <tbody>
                    {senders.map((s) => (
                      <tr key={s.email} className="border-t border-ink-100">
                        <td className="p-2">{s.email}</td>
                        <td className="p-2">{s.display_name}</td>
                        <td className="p-2">{s.is_admin ? "Y" : ""}</td>
                        <td className="p-2">{s.is_active ? "Y" : "N"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <input
                  className="input"
                  placeholder="Gmail"
                  value={newSender.email}
                  onChange={(e) => setNewSender({ ...newSender, email: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="표시 이름"
                  value={newSender.display_name}
                  onChange={(e) => setNewSender({ ...newSender, display_name: e.target.value })}
                />
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={newSender.is_admin}
                    onChange={(e) => setNewSender({ ...newSender, is_admin: e.target.checked })}
                  />
                  관리자
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={newSender.is_active}
                    onChange={(e) => setNewSender({ ...newSender, is_active: e.target.checked })}
                  />
                  활성
                </label>
              </div>
              <button className="btn-primary" onClick={saveSender}>
                등록 / 수정
              </button>
            </div>
          )}
          </div>
        </section>
      </main>
    </div>
  );
}