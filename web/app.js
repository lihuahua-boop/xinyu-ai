/* 心屿 AI 前端：无构建步骤，直接跑。 */

var state = {
  config: null,
  userId: null,
  character: null,
  messages: [],
  questions: [],
  templates: [],
  relationTypes: [],
  personaParams: [],
  appearance: {},
  sending: false,
  wizard: {
    step: 0,
    data: { relation_type: "boyfriend", name: "", appearance: {}, template_key: "gentle_healer" },
    question: null,
    busy: false
  }
};

var STORE_KEY = "xinyu.session";

function $(id) { return document.getElementById(id); }

function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

var API_BASE = window.API_BASE || "";

function api(path, options) {
  options = options || {};
  var config = { method: options.method || "GET", headers: {} };
  if (options.body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.body);
  }
  var url = API_BASE + path;
  return fetch(url, config).then(function (response) {
    return response.text().then(function (text) {
      var data = null;
      try { data = text ? JSON.parse(text) : null; } catch (error) { data = { message: text }; }
      if (!response.ok) {
        var message = (data && (data.message || data.detail)) || "请求失败";
        throw new Error(typeof message === "string" ? message : "请求失败");
      }
      return data;
    });
  });
}

function toast(text) {
  var node = $("toast");
  node.textContent = text;
  node.classList.add("show");
  clearTimeout(node._timer);
  node._timer = setTimeout(function () { node.classList.remove("show"); }, 2600);
}

function showView(name) {
  ["boot", "view-onboarding", "view-chat", "view-voice", "view-memory", "view-profile"].forEach(function (id) {
    var node = $(id);
    if (node) node.classList.add("hidden");
  });
  if (name === "onboarding") $("view-onboarding").classList.remove("hidden");
  else if (name === "chat") $("view-chat").classList.remove("hidden");
  else if (name === "voice") { $("view-voice").classList.remove("hidden"); startVoiceDemo(); }
  else if (name === "memory") $("view-memory").classList.remove("hidden");
  else if (name === "profile") $("view-profile").classList.remove("hidden");
  var tabbar = $("tabbar");
  if (name === "chat" || name === "onboarding" || name === "boot" || name === "voice") tabbar.classList.add("hidden");
  else tabbar.classList.remove("hidden");
  Array.prototype.forEach.call(tabbar.children, function (tab) {
    tab.classList.toggle("active", tab.dataset.view === name);
  });
}

function saveSession() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({
      userId: state.userId, characterId: state.character && state.character.id
    }));
  } catch (error) { /* 隐私模式下忽略 */ }
}

function readSession() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
  } catch (error) { return {}; }
}

function boot() {
  Promise.all([
    api("/api/meta/config"),
    api("/api/meta/interview"),
    api("/api/meta/templates"),
    api("/api/meta/relation-types"),
    api("/api/meta/persona-params"),
    api("/api/meta/appearance")
  ]).then(function (result) {
    state.config = result[0];
    state.questions = result[1].items;
    state.templates = result[2].items;
    state.relationTypes = result[3].items;
    state.personaParams = result[4].items;
    state.appearance = result[5];
    var session = readSession();
    var params = new URLSearchParams(window.location.search);
    if (params.get("user_id") && params.get("character_id")) {
      session = { userId: params.get("user_id"), characterId: params.get("character_id") };
    }
    if (session.userId && session.characterId) {
      return api("/api/characters/" + session.characterId).then(function (character) {
        state.userId = session.userId;
        state.character = character;
        saveSession();
        enterApp();
      }).catch(function () { startOnboarding(); });
    }
    startOnboarding();
  }).catch(function (error) {
    $("boot").querySelector(".boot-loading").textContent = "启动失败：" + error.message;
  });
}

function startOnboarding() {
  state.wizard = {
    step: 0,
    data: { relation_type: "boyfriend", name: "", appearance: {}, template_key: "gentle_healer" },
    question: null,
    busy: false
  };
  showView("onboarding");
  renderWizard();
}

function renderSteps() {
  var wrap = $("ob-steps");
  wrap.innerHTML = "";
  for (var i = 0; i < 4; i++) {
    var bar = el("span");
    if (i <= state.wizard.step) bar.className = "on";
    wrap.appendChild(bar);
  }
}

function renderWizard() {
  renderSteps();
  var body = $("ob-body");
  body.innerHTML = "";
  var step = state.wizard.step;
  $("ob-back").style.visibility = step === 0 ? "hidden" : "visible";
  $("ob-next").textContent = step === 3 ? "完成" : (step === 2 ? "开始认识我" : "下一步");
  $("ob-next").disabled = true;

  if (step === 0) renderStepRelation(body);
  else if (step === 1) renderStepAppearance(body);
  else if (step === 2) renderStepTemplate(body);
  else renderStepInterview(body);
}

function optionButton(label, desc, active, onPick) {
  var button = el("button", "option" + (active ? " on" : ""));
  button.appendChild(el("span", "option-label", label));
  if (desc) button.appendChild(el("span", "option-desc", desc));
  button.addEventListener("click", onPick);
  return button;
}

function renderStepRelation(body) {
  var group = el("div", "group");
  group.appendChild(el("div", "group-title", "你想让他以什么身份陪着你？"));
  var options = el("div", "options");
  state.relationTypes.forEach(function (item) {
    options.appendChild(optionButton(item.label, item.desc,
      state.wizard.data.relation_type === item.key, function () {
        state.wizard.data.relation_type = item.key;
        if (item.key === "safe_haven") state.wizard.data.template_key = "quiet_listener";
        renderWizard();
      }));
  });
  group.appendChild(options);
  body.appendChild(group);
  $("ob-next").disabled = false;
}

function renderStepAppearance(body) {
  var data = state.wizard.data;
  var nameGroup = el("div", "group");
  nameGroup.appendChild(el("div", "group-title", "他叫什么名字？"));
  var field = el("div", "field");
  var input = el("input");
  input.type = "text";
  input.maxLength = 16;
  input.placeholder = "比如：沈屿";
  input.value = data.name || "";
  input.addEventListener("input", function () {
    data.name = input.value.trim();
    $("ob-next").disabled = data.name.length < 1;
  });
  field.appendChild(input);
  nameGroup.appendChild(field);
  body.appendChild(nameGroup);

  var groups = [
    { key: "vibe", title: "他的气质", options: state.appearance.vibe || [] },
    { key: "style", title: "他常穿什么", options: state.appearance.style || [] },
    {
      key: "hairstyle",
      title: "发型",
      options: (state.appearance.hairstyle || []).map(function (item) { return item.label; }),
      values: (state.appearance.hairstyle || []).map(function (item) { return item.key; })
    },
    { key: "age_range", title: "年龄感", options: state.appearance.age_range || [] }
  ];
  groups.forEach(function (group) {
    var wrap = el("div", "group");
    wrap.appendChild(el("div", "group-title", group.title));
    var options = el("div", "options");
    group.options.forEach(function (label, index) {
      var value = group.values ? group.values[index] : label;
      options.appendChild(optionButton(label, "", data.appearance[group.key] === value, function () {
        data.appearance[group.key] = value;
        renderWizard();
      }));
    });
    wrap.appendChild(options);
    body.appendChild(wrap);
  });
  $("ob-next").disabled = (data.name || "").length < 1;
}

function renderStepTemplate(body) {
  var group = el("div", "group");
  group.appendChild(el("div", "group-title", "先给他一个起点，之后他会越来越像他自己"));
  var options = el("div", "options");
  state.templates.forEach(function (item) {
    options.appendChild(optionButton(item.label, item.tagline,
      state.wizard.data.template_key === item.key, function () {
        state.wizard.data.template_key = item.key;
        renderWizard();
      }));
  });
  group.appendChild(options);
  body.appendChild(group);
  $("ob-next").disabled = false;
}

function renderStepInterview(body) {
  var question = state.wizard.question;
  if (!question) {
    var done = el("div", "group");
    done.appendChild(el("div", "question", "他会记住你今天说的每一条。"));
    done.appendChild(el("p", "question-hint", "之后你随时可以在「他」这一页调整。"));
    body.appendChild(done);
    $("ob-next").disabled = false;
    return;
  }
  var group = el("div", "group");
  group.appendChild(el("div", "question", question.question));
  group.appendChild(el("p", "question-hint", question.hint || ""));
  var options = el("div", "options");
  question.options.forEach(function (option) {
    var button = optionButton(option.label, "", false, function () {
      if (state.wizard.busy) return;
      state.wizard.busy = true;
      api("/api/characters/" + state.character.id + "/interview", {
        method: "POST",
        body: { user_id: state.userId, question_key: question.key, option_key: option.key }
      }).then(function (character) {
        state.character = character;
        state.wizard.question = character.interview.next_question;
        state.wizard.busy = false;
        toast("他记住了：" + option.label);
        renderWizard();
      }).catch(function (error) {
        state.wizard.busy = false;
        toast(error.message);
      });
    });
    options.appendChild(button);
  });
  group.appendChild(options);
  body.appendChild(group);
  $("ob-next").disabled = true;
}

function ensureUser() {
  if (state.userId) return Promise.resolve(state.userId);
  return api("/api/users", {
    method: "POST",
    body: { nickname: "", age_verified: true }
  }).then(function (user) {
    state.userId = user.id;
    return user.id;
  });
}

function wizardNext() {
  var wizard = state.wizard;
  if (wizard.step === 2 && !state.character) {
    $("ob-next").disabled = true;
    return ensureUser().then(function () {
      return api("/api/characters", {
        method: "POST",
        body: {
          user_id: state.userId,
          name: wizard.data.name || "他",
          relation_type: wizard.data.relation_type,
          template_key: wizard.data.template_key,
          appearance: wizard.data.appearance || {},
          persona: {}
        }
      });
    }).then(function (character) {
      state.character = character;
      wizard.step = 3;
      wizard.question = state.questions[0] || null;
      saveSession();
      renderWizard();
    }).catch(function (error) {
      toast(error.message);
      $("ob-next").disabled = false;
    });
  } else if (wizard.step === 3) {
    enterApp();
  } else if (wizard.step < 2) {
    wizard.step += 1;
    renderWizard();
  }
}

function enterApp() {
  showView("chat");
  renderTopbar();
  loadMessages().then(function () {
    return api("/api/characters/" + state.character.id + "/proactive?materialize_now=1");
  }).then(function (data) {
    if (data && data.created && data.created.length) {
      data.created.forEach(function (item) {
        toast("他主动找你了：" + item.kind_label);
      });
      return loadMessages();
    }
  }).catch(function () { /* 主动陪伴失败不影响聊天 */ });
  refreshCharacter();
}

function refreshCharacter() {
  if (!state.character) return Promise.resolve();
  return api("/api/characters/" + state.character.id).then(function (character) {
    state.character = character;
    renderTopbar();
    renderProfile();
  }).catch(function () { });
}

function renderTopbar() {
  var character = state.character;
  if (!character) return;
  $("chat-name").textContent = character.name;
  var pill = $("chat-memory");
  var last = null;
  for (var i = state.messages.length - 1; i >= 0; i--) {
    var m = state.messages[i];
    if (m.role === "assistant" && m.memories_used && m.memories_used.length) { last = m.memories_used; break; }
  }
  if (!last || !last.length) { pill.classList.add("hidden"); pill.textContent = ""; return; }
  var label = "想起" + (last[0].category_label || "记忆");
  if (last.length > 1) label += " · 还想到" + (last.length - 1) + "件";
  pill.textContent = label; pill.classList.remove("hidden");
}

function loadMessages() {
  return api("/api/characters/" + state.character.id + "/messages?limit=80").then(function (data) {
    state.messages = data.items || [];
    renderMessages();
  });
}

/* 聊天里只展示最相关的一条记忆，其余收进记忆页——
   一口气铺五张卡片会像调试面板，而不是陪伴。 */
function renderEchoCards(wrap, memories, limit) {
  var list = memories || [];
  var max = limit || 1;
  list.slice(0, max).forEach(function (memory) {
    var card = el("div", "echo-card");
    card.appendChild(el("b", null, "他想起：" + (memory.category_label || "记忆")));
    card.appendChild(el("div", null, memory.content));
    wrap.appendChild(card);
  });
  if (list.length > max) {
    wrap.appendChild(el("div", "echo-more", "他还想到 " + (list.length - max) + " 件相关的事"));
  }
}

function fmtTime(iso) {
  if (!iso) return "";
  var d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  var hh = ("0" + d.getHours()).slice(-2);
  var mm = ("0" + d.getMinutes()).slice(-2);
  return hh + ":" + mm;
}

  function renderMessage(message) {
    var isUser = message.role === "user";
    var node = el("div", "msg " + (isUser ? "user" : "assistant"));
    var row = el("div", "msg-row");
    if (isUser && message.created_at) row.appendChild(el("span", "msg-time", fmtTime(message.created_at)));
    row.appendChild(el("div", "bubble", message.content));
    if (isUser) row.appendChild(el("div", "msg-avatar"));
    else if (message.created_at) row.appendChild(el("span", "msg-time", fmtTime(message.created_at)));
    node.appendChild(row);
    var meta = el("div", "msg-meta");
    meta.appendChild(el("span", "msg-read", "已读"));
  if (!isUser && message.safety_flag) meta.appendChild(el("span", "tag safety", "安全通道"));
  if (!isUser && message.proactive) meta.appendChild(el("span", "tag proactive", "主动找你"));
  node.appendChild(meta);
  return node;
}

function renderMessages() {
  var wrap = $("messages");
  wrap.innerHTML = "";
  if (!state.messages.length) {
    var hint = el("div", "msg assistant");
    var hintRow = el("div", "msg-row");
    hintRow.appendChild(el("div", "bubble", "我在。今天想聊点什么，还是先陪你待一会儿？"));
    hint.appendChild(hintRow);
    wrap.appendChild(hint);
  }
  state.messages.forEach(function (message) {
    wrap.appendChild(renderMessage(message));
  });
  wrap.scrollTop = wrap.scrollHeight;
}

function sendMessage() {
  var input = $("composer-input");
  var text = input.value.trim();
  if (!text || state.sending || !state.character) return;
  state.sending = true;
  input.value = "";
  input.style.height = "auto";
  state.messages.push({ role: "user", content: text, created_at: new Date().toISOString() });
  renderMessages();

  var typing = el("div", "msg assistant");
  var trow = el("div", "msg-row");
  var bubble = el("div", "bubble");
  var dots = el("div", "typing");
  dots.appendChild(el("i"));
  dots.appendChild(el("i"));
  dots.appendChild(el("i"));
  bubble.appendChild(dots);
  trow.appendChild(bubble);
  typing.appendChild(trow);
  $("messages").appendChild(typing);
  $("messages").scrollTop = $("messages").scrollHeight;
  $("composer-tip").textContent = "他正在回你…";

  streamChat(text, typing).catch(function (error) {
    typing.remove();
    state.sending = false;
    $("composer-tip").textContent = "";
    toast(error.message);
  });
}

function streamChat(text, typing) {
  var characterId = state.character.id;
  return fetch(API_BASE + "/api/characters/" + characterId + "/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: state.userId, text: text })
  }).then(function (resp) {
    if (!resp.ok) {
      return resp.json().then(function (err) {
        throw new Error(err.message || err.detail || "请求失败");
      });
    }
    return readStream(resp.body, typing);
  }).catch(function (streamError) {
    // 流式失败就退回普通接口，保证一定能回上话
    return api("/api/characters/" + characterId + "/chat", {
      method: "POST",
      body: { user_id: state.userId, text: text }
    }).then(function (data) {
      typing.remove();
      handleResult(data, null);
    }).catch(function () {
      throw streamError;
    });
  });
}

function readStream(body, typing) {
  var reader = body.getReader();
  var decoder = new TextDecoder("utf-8");
  var buffer = "";
  var streaming = null;
  var reply = "";

  function applyFrame(payload) {
    if (payload.event === "token") {
      reply += payload.data.content || "";
      if (!streaming) {
        typing.remove();
        streaming = el("div", "msg assistant");
        var row = el("div", "msg-row");
        row.appendChild(el("div", "bubble", ""));
        streaming.appendChild(row);
        $("messages").appendChild(streaming);
      }
      streaming.querySelector(".bubble").textContent = reply;
      $("messages").scrollTop = $("messages").scrollHeight;
    } else if (payload.event === "done") {
      handleResult(payload.data, streaming);
    }
  }

  function pump() {
    return reader.read().then(function (result) {
      if (result.done) {
        if (buffer.trim()) {
          parseFrames(buffer);
          buffer = "";
        }
        return;
      }
      buffer += decoder.decode(result.value, { stream: true });
      var frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      frames.forEach(parseFrames);
      return pump();
    });
  }

  function parseFrames(frame) {
    frame = frame.trim();
    if (frame.indexOf("data:") !== 0) return;
    try {
      applyFrame(JSON.parse(frame.slice(5).trim()));
    } catch (error) { /* 忽略坏帧 */ }
  }

  return pump().then(function () {
    if (!streaming && !reply) {
      throw new Error("没有收到回复");
    }
  });
}

function handleResult(data, streaming) {
  state.sending = false;
  state.messages.push({
    role: "assistant",
    content: data.reply,
    memories_used: data.memories_used,
    safety_flag: data.safety && data.safety.level === "high" ? "high" : "",
    created_at: new Date().toISOString()
  });

  if (streaming === null) {
    renderMessages();
  }

  var tip = "他察觉到的情绪：" + data.emotion.label;
  if (data.memories_written) tip += " · 又记下 " + data.memories_written + " 件事";
  $("composer-tip").textContent = tip;

  state.character.relationship = data.relationship;
  renderTopbar();
  if (data.relationship.stage_changed) {
    toast("你们的关系进入「" + data.relationship.stage_label + "」");
  } else if (data.relationship.intimacy_gain >= 1.2) {
    toast("亲密度 +" + data.relationship.intimacy_gain);
  }
}

function renderMemory() {
  if (!state.character) return Promise.resolve();
  return api("/api/characters/" + state.character.id + "/memories").then(function (data) {
    var stats = data.stats || { total: 0, by_category: {} };
    $("memory-sub").textContent = stats.total
      ? "他已经记住 " + stats.total + " 件事，都是你说过的。"
      : "还没有记忆，多跟他说说话。";

    var statsWrap = $("memory-stats");
    statsWrap.innerHTML = "";
    var summary = el("div", "stat");
    summary.appendChild(el("b", null, String(stats.total)));
    summary.appendChild(el("span", null, "总记忆"));
    statsWrap.appendChild(summary);
    Object.keys(data.labels || {}).forEach(function (key) {
      var count = (stats.by_category || {})[key] || 0;
      if (!count) return;
      var stat = el("div", "stat");
      stat.appendChild(el("b", null, String(count)));
      stat.appendChild(el("span", null, data.labels[key]));
      statsWrap.appendChild(stat);
    });

    var list = $("memory-list");
    list.innerHTML = "";
    if (!data.items || !data.items.length) {
      list.appendChild(el("p", "page-sub", "这里会慢慢长出关于你的东西。"));
      return;
    }
    var grouped = {};
    data.items.forEach(function (item) {
      grouped[item.category] = grouped[item.category] || [];
      grouped[item.category].push(item);
    });
    Object.keys(grouped).forEach(function (category) {
      list.appendChild(el("div", "memory-group-title", data.labels[category] || category));
      grouped[category].forEach(function (item) {
        var row = el("div", "memory-item");
        row.appendChild(el("p", null, item.content));
        row.appendChild(el("span", "importance", "重要度 " + Math.round((item.importance || 0) * 100)));
        var button = el("button", null, "让他忘掉");
        button.addEventListener("click", function () {
          api("/api/memories/" + item.id, { method: "DELETE" }).then(function () {
            toast("他忘掉了这件事");
            renderMemory();
            refreshCharacter();
          }).catch(function (error) { toast(error.message); });
        });
        row.appendChild(button);
        list.appendChild(row);
      });
    });
  }).catch(function (error) { toast(error.message); });
}

function renderProfile() {
  var character = state.character;
  if (!character || $("view-profile").classList.contains("hidden")) return;
  var relationship = character.relationship || {};
  $("profile-name").textContent = character.name;
  $("profile-sub").textContent = character.template_label + " · " + (character.persona_tags || []).join(" · ");

  var block = $("relation-block");
  block.innerHTML = "";
  var memoryCount = (character.memory && character.memory.total) || 0;
  var rows = [
    ["关系", character.relation_label],
    ["阶段", relationship.stage_label || "初识"],
    ["亲密度", Math.round(relationship.intimacy || 0) + " / 100"],
    ["认识", (relationship.days_together || 1) + " 天"],
    ["记忆", memoryCount + " 件事"]
  ];
  rows.forEach(function (row) {
    var line = el("div", "relation-row");
    line.appendChild(el("span", null, row[0]));
    line.appendChild(el("span", null, String(row[1])));
    block.appendChild(line);
  });
  (relationship.milestones || []).slice(-4).forEach(function (item) {
    block.appendChild(el("div", "milestone", item.title + " · " + (item.content || "")));
  });

  var labels = { happy: "开心", excited: "期待", sad: "难过", anxious: "焦虑",
    lonely: "孤独", tired: "疲惫", angry: "生气", crisis: "需要被接住",
    affection: "想亲近", calm: "平静", neutral: "说不清" };
  var mood = $("mood-strip");
  mood.innerHTML = "";
  var recent = state.messages.filter(function (item) { return item.role === "user"; }).slice(-8);
  if (!recent.length) mood.appendChild(el("span", "mood-pill", "还没聊过"));
  recent.forEach(function (item) {
    mood.appendChild(el("span", "mood-pill", labels[item.emotion] || "说不清"));
  });

  var sliders = $("persona-sliders");
  sliders.innerHTML = "";
  state.personaParams.forEach(function (param) {
    var row = el("div", "slider-row");
    var label = el("label");
    label.appendChild(el("span", null, param.label));
    var value = el("b", null, String(character.persona[param.key]));
    label.appendChild(value);
    row.appendChild(label);
    var input = el("input");
    input.type = "range";
    input.min = "0";
    input.max = "100";
    input.value = character.persona[param.key];
    input.dataset.key = param.key;
    input.addEventListener("input", function () { value.textContent = input.value; });
    row.appendChild(input);
    var hint = el("div", "slider-hint", Number(character.persona[param.key]) >= 50 ? param.high : param.low);
    row.appendChild(hint);
    sliders.appendChild(row);
  });

  $("profile-avatar").src = character.avatar_url;
  var appearance = character.appearance || {};
  var details = [];
  if (appearance.vibe) details.push("气质：" + appearance.vibe);
  if (appearance.style) details.push("穿着：" + appearance.style);
  if (appearance.age_range) details.push("年龄感：" + appearance.age_range);
  $("avatar-meta").textContent = details.length ? details.join("｜") : "还没有设定外观";
}

function savePersona() {
  var payload = {};
  Array.prototype.forEach.call($("persona-sliders").querySelectorAll("input[type=range]"), function (input) {
    payload[input.dataset.key] = Number(input.value);
  });
  api("/api/characters/" + state.character.id, { method: "PATCH", body: { persona: payload } })
    .then(function (character) {
      state.character = character;
      renderProfile();
      renderTopbar();
      toast("人格已更新，他说话会跟着变");
    }).catch(function (error) { toast(error.message); });
}

var _voiceRec = null;
var _voiceSpeaking = false;
var _voiceSupported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);

function startVoiceDemo() {
  stopVoiceDemo();
  showVoiceHint("Hold and speak", "按住说话");
}

function stopVoiceDemo() {
  if (_voiceRec) { try { _voiceRec.abort(); } catch (e) {} _voiceRec = null; }
  if (_voiceSpeaking) { try { if (_voiceAudio) { _voiceAudio.pause(); _voiceAudio.currentTime = 0; } } catch (e) {} _voiceSpeaking = false; }
}

function showVoiceHint(en, zh) {
  var e = $("voice-en"), z = $("voice-zh");
  if (e) e.textContent = en;
  if (z) z.textContent = zh;
}

function startRecognition() {
  if (!_voiceSupported) { toast("浏览器不支持语音识别"); return; }
  if (_voiceSpeaking) { if (_voiceAudio) { _voiceAudio.pause(); _voiceAudio.currentTime = 0; } _voiceSpeaking = false; }
  var Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  _voiceRec = new Ctor();
  _voiceRec.lang = "zh-CN";
  _voiceRec.continuous = false;
  _voiceRec.interimResults = true;
  _voiceRec.onresult = function (ev) {
    var text = "";
    for (var i = ev.resultIndex; i < ev.results.length; i++) text += ev.results[i][0].transcript;
    showVoiceHint(text, text);
  };
  _voiceRec.onend = function () {
    var text = ($("voice-zh") || {}).textContent || "";
    if (text && text !== "按住说话" && text.length > 1) sendVoiceText(text);
  };
  _voiceRec.onerror = function () { $("voice-mic").classList.remove("listening"); $("voice-orb").classList.remove("listening"); };
  _voiceRec.start();
  $("voice-mic").classList.add("listening");
  $("voice-orb").classList.add("listening");
  showVoiceHint("Listening…", "聆听中…");
}

function stopRecognition() {
  if (_voiceRec) { try { _voiceRec.stop(); } catch (e) {} }
  $("voice-mic").classList.remove("listening");
  $("voice-orb").classList.remove("listening");
}

function sendVoiceText(text) {
  showVoiceHint("Thinking…", "想想…");
  api("/api/characters/" + state.character.id + "/chat", {
    method: "POST", body: { user_id: state.userId, text: text }
  }).then(function (data) {
    showVoiceHint(data.reply, data.reply);
    speakVoice(data.reply);
    state.character.relationship = data.relationship;
  }).catch(function (err) { showVoiceHint("Try again", err.message); });
}

// TTS 声音选择，持久化到 localStorage
var TTS_VOICE = localStorage.getItem("tts_voice") || "xiaoxiao";
var TTS_SPEED = parseFloat(localStorage.getItem("tts_speed")) || 1.0;

function speakVoice(text) {
  if (!text) return;
  var url = "/api/tts?text=" + encodeURIComponent(text)
          + "&voice=" + TTS_VOICE + "&speed=" + TTS_SPEED;
  var audio = new Audio(url);
  audio.onplay = function () { _voiceSpeaking = true; };
  audio.onended = function () { _voiceSpeaking = false; showVoiceHint("Hold and speak", "按住说话"); };
  audio.onerror = function () { _voiceSpeaking = false; showVoiceHint("Hold and speak", "按住说话"); };
  _voiceAudio = audio;
  audio.play().catch(function () { _voiceSpeaking = false; });
}

// 暴露给调试/设置页
window.setTtsVoice = function (v) { TTS_VOICE = v; localStorage.setItem("tts_voice", v); };
window.setTtsSpeed = function (s) { TTS_SPEED = parseFloat(s); localStorage.setItem("tts_speed", s); };

function bind() {
  $("ob-next").addEventListener("click", wizardNext);
  $("ob-back").addEventListener("click", function () {
    if (state.wizard.step > 0) {
      state.wizard.step -= 1;
      renderWizard();
    }
  });
  $("composer-send").addEventListener("click", sendMessage);
  $("composer-input").addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
  $("composer-input").addEventListener("input", function () {
    var input = $("composer-input");
    input.style.height = "auto";
    input.style.height = Math.min(120, input.scrollHeight) + "px";
  });
  $("memory-add").addEventListener("click", function () {
    var text = $("memory-input").value.trim();
    if (!text) return;
    api("/api/characters/" + state.character.id + "/memories", {
      method: "POST",
      body: { category: $("memory-category").value, content: text, importance: 0.85 }
    }).then(function () {
      $("memory-input").value = "";
      toast("他记住了");
      renderMemory();
      refreshCharacter();
    }).catch(function (error) { toast(error.message); });
  });
  $("persona-save").addEventListener("click", savePersona);
  $("chat-back").addEventListener("click", function () {
    toggleMenu(false);
    showView("profile");
    refreshCharacter();
    renderProfile();
  });
  $("chat-menu").addEventListener("click", function (event) {
    event.stopPropagation();
    toggleMenu();
  });
  Array.prototype.forEach.call($("chat-menu-pop").children, function (item) {
    item.addEventListener("click", function () {
      var act = item.dataset.act;
      toggleMenu(false);
      if (act === "voice") { showView("voice"); }
      if (act === "memory") {
        showView("memory");
        renderMemory();
      }
      if (act === "profile") {
        showView("profile");
        refreshCharacter();
        renderProfile();
      }
    });
  });
  document.addEventListener("click", function () { toggleMenu(false); });
  $("voice-back").addEventListener("click", function () { stopVoiceDemo(); showView("chat"); });
  // 声音设置面板
  var SETTINGS_VOICES = [
    { key: "xiaoxiao",   zh: "晓晓",   tag: "温柔" },
    { key: "xiaoyi",     zh: "晓伊",   tag: "甜美" },
    { key: "xiaochen",   zh: "晓辰",   tag: "知性" },
    { key: "xiaomo",     zh: "晓墨",   tag: "文艺" },
    { key: "xiaoshuang", zh: "晓双",   tag: "活泼" },
    { key: "yunxi",      zh: "云希",   tag: "清朗男声" },
    { key: "yunyang",    zh: "云扬",   tag: "阳光男声" },
  ];
  function renderVoiceList() {
    var list = $("voice-list"); if (!list) return;
    list.innerHTML = "";
    SETTINGS_VOICES.forEach(function (v) {
      var btn = document.createElement("div");
      btn.className = "voice-item" + (v.key === TTS_VOICE ? " selected" : "");
      btn.innerHTML = v.zh + '<div class="voice-en">' + v.tag + '</div>';
      btn.onclick = function () {
        TTS_VOICE = v.key; localStorage.setItem("tts_voice", v.key);
        renderVoiceList();
        // 试听
        var audio = new Audio("/api/tts?text=" + encodeURIComponent("你好呀，我是" + v.zh) + "&voice=" + v.key + "&speed=" + TTS_SPEED);
        audio.play().catch(function () {});
      };
      list.appendChild(btn);
    });
  }
  $("voice-settings").addEventListener("click", function () {
    renderVoiceList();
    $("voice-panel").classList.remove("hidden");
    $("voice-panel-mask").classList.remove("hidden");
  });
  function closeVoicePanel() {
    $("voice-panel").classList.add("hidden");
    $("voice-panel-mask").classList.add("hidden");
  }
  $("voice-panel-mask").addEventListener("click", closeVoicePanel);
  var speedSlider = $("voice-speed");
  if (speedSlider) {
    speedSlider.value = TTS_SPEED;
    speedSlider.oninput = function () {
      TTS_SPEED = parseFloat(this.value);
      localStorage.setItem("tts_speed", TTS_SPEED);
      $("voice-speed-val").textContent = TTS_SPEED.toFixed(1) + "x";
    };
    $("voice-speed-val").textContent = TTS_SPEED.toFixed(1) + "x";
  }

  var mic = $("voice-mic");
  if (mic) {
    mic.addEventListener("mousedown", startRecognition);
    mic.addEventListener("mouseup", stopRecognition);
    mic.addEventListener("mouseleave", stopRecognition);
    mic.addEventListener("touchstart", function (e) { e.preventDefault(); startRecognition(); });
    mic.addEventListener("touchend", function (e) { e.preventDefault(); stopRecognition(); });
  }
  $("logout").addEventListener("click", function () {
    try { localStorage.removeItem(STORE_KEY); } catch (error) { /* ignore */ }
    state.userId = null;
    state.character = null;
    state.messages = [];
    startOnboarding();
  });
  Array.prototype.forEach.call($("tabbar").children, function (tab) {
    tab.addEventListener("click", function () {
      var view = tab.dataset.view;
      showView(view);
      if (view === "memory") renderMemory();
      if (view === "profile") { refreshCharacter(); renderProfile(); }
      if (view === "chat") loadMessages();
    });
  });
}

function toggleMenu(force) {
  var pop = $("chat-menu-pop");
  if (!pop) return;
  var show = force === undefined ? pop.classList.contains("hidden") : force;
  if (show) pop.classList.remove("hidden");
  else pop.classList.add("hidden");
}

bind();
boot();
