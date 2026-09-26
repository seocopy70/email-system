"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { api, AuthUser, fileToBase64, setAuthToken, setUnauthorizedHandler } from "@/lib/api";

type BodyMode = "html" | "text" | "both";
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
const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 9l6 6 6-6" />
  </svg>
);

// 변수 태그를 한 줄로 늘어놓는 대신, 클릭하면 열리는 목록에서 골라 커서 위치에 끼워 넣는 메뉴
function VarMenu({ tags, onPick }: { tags: { label: string; tag: string }[]; onPick: (tag: string) => void }) {
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
        변수 삽입
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
              onClick={() => {
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

export default function Home() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [password, setPassword] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginName, setLoginName] = useState("");
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
  const [useBodyImage, setUseBodyImage] = useState(false);

  const [previewHtml, setPreviewHtml] = useState("");
  const [previewSubj, setPreviewSubj] = useState("");

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
  const [topicMsg, setTopicMsg] = useState("");
  const lastEnteredTopic = useRef<number | null>(null);
  const subjectRef = useRef<HTMLInputElement>(null);
  const plainRef = useRef<HTMLTextAreaElement>(null);
  const htmlRef = useRef<HTMLTextAreaElement>(null);
  const footerRef = useRef<HTMLTextAreaElement>(null);

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
      })
      .catch(() => {});
  }, [user, refreshTopics]);

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
          footer_image_width_pct: footerImageWidth,
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
  ]);

  useEffect(() => {
    if (!user || bottomTab !== "stats") return;
    api.stats().then(setStats).catch(console.error);
  }, [user, bottomTab]);

  useEffect(() => {
    if (!user || !topicId || bottomTab !== "logs") return;
    api.topicLogs(topicId).then(setLogs).catch(console.error);
  }, [user, topicId, bottomTab]);

  useEffect(() => {
    if (!user || !user.is_admin || bottomTab !== "admin") return;
    api.senders().then(setSenders).catch(console.error);
  }, [user, bottomTab]);

  async function doLogin() {
    setLoginErr("");
    setBusy(true);
    try {
      const u = await api.login(loginEmail, password, loginName || undefined);
      setAuthToken(u.token); // 이후 요청이 인증되도록 user 설정보다 먼저
      setUser(u);
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
    setBodyMode((p.body_mode as BodyMode) || "html");
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
    setBodyMode((t.body_mode as BodyMode) || "html");
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
    if (field === "subject") applyAt(subjectRef.current, subject, setSubject);
    if (field === "plain") applyAt(plainRef.current, plainBody, setPlainBody);
    if (field === "html") applyAt(htmlRef.current, htmlBody, setHtmlBody);
    if (field === "footer") applyAt(footerRef.current, footerText, setFooterText);
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

  async function saveMyPrefs() {
    if (!user) return;
    await api.savePrefs(user.email, {
      footer_mode: footerMode,
      footer_text: footerText,
      footer_image_b64: footerImageB64,
      footer_image_width: footerImageWidth,
      use_footer_image: footerMode === "image",
      body_mode: bodyMode,
    });
    alert("기본 설정을 저장했습니다.");
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

  // 발송 기록이 하나라도 있는 주제는 지우지 않는다 (서버도 한 번 더 막는다)
  async function requestDeleteTopic() {
    if (topicId == null) return;
    setTopicMsg("");
    try {
      const st = await api.topicStatus(topicId);
      if (Object.keys(st || {}).length > 0) {
        setConfirmDelTopic(false);
        setTopicMsg("이미 발송 기록이 있는 주제는 삭제할 수 없습니다. 발송 내역은 그대로 보존됩니다.");
        return;
      }
      setConfirmDelTopic(true);
    } catch (e: any) {
      setTopicMsg(e.message || "확인하지 못했습니다");
    }
  }

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
    // 눌렀을 때 바로 확인: 제목/본문이 비어 있으면 보내지 않는다
    const needText = bodyMode === "text" || bodyMode === "both";
    const needHtml = bodyMode === "html" || bodyMode === "both";
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
        footer_image_width_pct: footerImageWidth,
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
        <div className="w-full max-w-md">
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
            <input className="input" placeholder="표시 이름 (선택)" autoComplete="off" value={loginName} onChange={(e) => setLoginName(e.target.value)} />
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

      <main className="max-w-[1400px] mx-auto p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="space-y-3">
          <div className="card p-4 space-y-2">
            <div className="card-title">발송 주제</div>
            <div className="flex gap-2">
              <select
                className="input"
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
              </button>
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
              <div className="card-title mb-0">메일 작성</div>
              <button type="button" className="text-xs text-ink-500 hover:text-ink-900" onClick={saveMyPrefs}>
                내 기본설정 저장
              </button>
            </div>
            <div className="flex gap-2">
              <select
                className="input"
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
              </button>
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

            <div className="flex justify-end">
              <VarMenu tags={varTags} onPick={(tag) => insertTag("subject", tag)} />
            </div>
            <input
              ref={subjectRef}
              className="input"
              aria-label="제목"
              placeholder={ex.subject || "제목"}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />

            <div className="doc-tabs">
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

            <div className="scroll-box h-[380px]">
            {activeTab === "body" && (
              <div className="space-y-2">
                <div className="seg">
                  {(
                    [
                      ["html", "HTML"],
                      ["text", "텍스트"],
                      ["both", "HTML+텍스트"],
                    ] as const
                  ).map(([k, label]) => (
                    <button key={k} type="button" data-active={bodyMode === k} onClick={() => setBodyMode(k)}>
                      {label}
                    </button>
                  ))}
                </div>
                {(bodyMode === "text" || bodyMode === "both") && (
                  <>
                    <div className="flex justify-end">
                      <VarMenu tags={varTags} onPick={(tag) => insertTag("plain", tag)} />
                    </div>
                    <textarea
                      ref={plainRef}
                      className="input min-h-[120px] font-mono text-xs"
                      aria-label="텍스트 본문"
                      placeholder={ex.plain_body}
                      value={plainBody}
                      onChange={(e) => setPlainBody(e.target.value)}
                    />
                  </>
                )}
                {(bodyMode === "html" || bodyMode === "both") && (
                  <>
                    <div className="flex justify-end">
                      <VarMenu tags={varTags} onPick={(tag) => insertTag("html", tag)} />
                    </div>
                    <textarea
                      ref={htmlRef}
                      className="input min-h-[140px] font-mono text-xs"
                      aria-label="HTML 본문"
                      placeholder={ex.html_body}
                      value={htmlBody}
                      onChange={(e) => setHtmlBody(e.target.value)}
                    />
                  </>
                )}
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={useBodyImage} onChange={(e) => setUseBodyImage(e.target.checked)} />
                  본문 이미지 사용
                </label>
                {useBodyImage && (
                  <div className="space-y-2 pl-1">
                    <input type="file" accept="image/*" onChange={(e) => onBodyImage(e.target.files?.[0] || null)} />
                    <p className="text-xs text-ink-500">
                      본문에 <code>{"{이미지}"}</code>를 넣으면 그 자리에, 없으면 본문 아래에 들어갑니다.
                    </p>
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
                    {bodyImageB64 && (
                      <img src={`data:image/png;base64,${bodyImageB64}`} alt="body" className="max-h-32 rounded border border-ink-200" />
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === "footer" && (
              <div className="space-y-2">
                <div className="seg">
                  {(
                    [
                      ["text", "텍스트"],
                      ["image", "이미지"],
                      ["none", "사용 안 함"],
                    ] as const
                  ).map(([k, label]) => (
                    <button key={k} type="button" data-active={footerMode === k} onClick={() => setFooterMode(k)}>
                      {label}
                    </button>
                  ))}
                </div>
                {footerMode !== "none" && (
                  <textarea
                    ref={footerRef}
                    className="input min-h-[72px]"
                    value={footerText}
                    onChange={(e) => setFooterText(e.target.value)}
                    placeholder="푸터 문구"
                  />
                )}
                {footerMode === "image" && (
                  <div className="space-y-2">
                    <input type="file" accept="image/*" onChange={(e) => onFooterImage(e.target.files?.[0] || null)} />
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
          </div>
        </section>

        <section className="card p-4 lg:sticky lg:top-4 lg:self-start h-fit space-y-2">
          <div className="card-title">실시간 미리보기</div>
          <div className="text-xs text-ink-500 bg-ink-50 border border-ink-200 rounded-lg px-3 py-2">
            <b>제목</b> {previewSubj || "—"}
          </div>
          <div className="bg-ink-100 rounded-lg border border-ink-200 overflow-hidden h-[70vh] min-h-[420px] max-h-[720px]">
            <iframe
              title="preview"
              className="w-full h-full bg-white"
              sandbox="allow-popups"
              srcDoc={previewHtml || "<p style='padding:16px;color:#888'>미리보기</p>"}
            />
          </div>
        </section>

        <section className="lg:col-span-2">
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
              <input type="file" accept=".xlsx,.xls" onChange={(e) => e.target.files?.[0] && onExcel(e.target.files[0])} />
              {recipients.length > 0 && (
                <>
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
                          return (
                            <tr key={r.recipient_id} className="border-t border-ink-100">
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
                              <td className="p-2 text-ink-500">{label}</td>
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
