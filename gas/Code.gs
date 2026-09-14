const SN = {
  ISSUES: 'ISSUES',
  SUBSCRIBERS: 'SUBSCRIBERS',
  EMAIL_LOG: 'EMAIL_LOG',
  RUN_LOG: 'RUN_LOG',
  AUTOMATION: 'AUTOMATION'
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Student News')
    .addItem('Approve Today', 'approveToday')
    .addItem('Retry Blocked', 'retryBlocked')
    .addItem('Publish Ready', 'publishReady')
    .addSeparator()
    .addItem('View Run Log', 'viewRunLog')
    .addItem('Email Delivery', 'sendPublishedIssueEmails')
    .addItem('Retry Failed Email', 'retryFailedEmails')
    .addToUi();
}

function approveToday() {
  const ctx = findTodayIssue_();
  if (!ctx) throw new Error('找不到今日 Issue。');
  assertReadyForApproval_(ctx.record);
  setIssueFields_(ctx.sheet, ctx.row, {
    Approval: 'YES',
    Next_Action: 'PUBLISH_PENDING'
  });
  SpreadsheetApp.getActive().toast('Approval = YES；尚未代表已發布。');
}

function publishReady() {
  const ctx = findTodayIssue_();
  if (!ctx) throw new Error('找不到今日 Issue。');
  assertReadyForApproval_(ctx.record);
  setIssueFields_(ctx.sheet, ctx.row, {
    Approval: 'YES',
    Next_Action: 'PUBLISH_PENDING'
  });
  const triggered = triggerAutomation_();
  SpreadsheetApp.getActive().toast(
    triggered
      ? '已核准並觸發 Automation；只有 webhook 成功後才會變成 PUBLISHED。'
      : '已核准；未設定 GitHub 即時觸發，下一次排程會處理發布。'
  );
}

function retryBlocked() {
  const ctx = selectedOrTodayIssue_();
  if (!ctx) throw new Error('找不到要 Retry 的 Issue。');
  const status = upper_(ctx.record.Status);
  if (status.indexOf('BLOCKED') !== 0) {
    throw new Error('只有 BLOCKED_* 狀態可 Retry。');
  }
  setIssueFields_(ctx.sheet, ctx.row, {
    Status: 'SCHEDULED',
    Fact_QA: 'PENDING',
    Teaching_QA: 'PENDING',
    Layout_QA: 'PENDING',
    Approval: 'PENDING',
    Last_Error: '',
    Blocked_Reason: '',
    Next_Action: 'RETRY'
  });
  const triggered = triggerAutomation_();
  SpreadsheetApp.getActive().toast(
    triggered ? '已重置 BLOCKED 狀態並觸發 Automation。' : '已重置；下一次排程會重新處理。'
  );
}

function viewRunLog() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SN.RUN_LOG);
  if (!sheet) throw new Error('缺少 RUN_LOG。');
  sheet.activate();
}

function setupEmailDeliveryTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'sendPublishedIssueEmails')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('sendPublishedIssueEmails')
    .timeBased()
    .everyMinutes(15)
    .create();
}

function sendPublishedIssueEmails() {
  deliverEmails_(['PENDING', 'FAILED', 'PARTIAL', '']);
}

function retryFailedEmails() {
  deliverEmails_(['FAILED', 'PARTIAL']);
}

function deliverEmails_(allowedEmailStatuses) {
  const ss = SpreadsheetApp.getActive();
  const issueSheet = mustSheet_(SN.ISSUES);
  const subscriberSheet = mustSheet_(SN.SUBSCRIBERS);
  const logSheet = mustSheet_(SN.EMAIL_LOG);

  const issueRows = records_(issueSheet);
  const subscribers = records_(subscriberSheet);

  issueRows.forEach(ctx => {
    const issue = ctx.record;
    if (upper_(issue.Status) !== 'PUBLISHED') return;
    if (allowedEmailStatuses.indexOf(upper_(issue.Email_Status)) < 0) return;
    if (!isHttp_(issue.HTML_URL) || !isHttp_(issue.PDF_URL)) return;

    const payloadUrl = String(issue.HTML_URL).replace(/\/index\.html(?:\?.*)?$/, '/email.json');
    if (payloadUrl === issue.HTML_URL) {
      setIssueFields_(issueSheet, ctx.row, {
        Email_Status: 'FAILED',
        Email_Error: 'Cannot derive email.json from HTML_URL'
      });
      return;
    }

    let payload;
    try {
      payload = fetchJson_(payloadUrl);
    } catch (err) {
      setIssueFields_(issueSheet, ctx.row, {
        Email_Status: 'FAILED',
        Email_Error: String(err)
      });
      appendRunLog_('EMAIL_DELIVERY', 'ERROR', issue.Issue_ID, String(err), payloadUrl);
      return;
    }

    const eligible = subscribers.filter(s =>
      shouldReceive_(s.record, issue.Language) && String(s.record.Email || '').trim()
    );
    let sent = 0;
    let alreadySent = 0;
    let failed = 0;
    const errors = [];

    eligible.forEach(subCtx => {
      const sub = subCtx.record;
      const email = String(sub.Email || '').trim();
      const key = emailKey_(issue.Issue_ID, email);
      if (emailAlreadySent_(logSheet, key)) {
        alreadySent += 1;
        return;
      }

      try {
        const options = buildMailOptions_(issue, payload, sub);
        MailApp.sendEmail(options);
        sent += 1;
        appendEmailLog_(logSheet, {
          Delivery_Key: key,
          Issue_ID: issue.Issue_ID,
          Recipient: email,
          Status: 'SENT',
          Sent_At: new Date(),
          Attachment: upper_(sub.PDF_Attach) === 'YES' ? issue.PDF_URL : '',
          Error: '',
          Version: issue.Version || payload.version || ''
        });
      } catch (err) {
        failed += 1;
        errors.push(email + ': ' + String(err));
        appendEmailLog_(logSheet, {
          Delivery_Key: key,
          Issue_ID: issue.Issue_ID,
          Recipient: email,
          Status: 'FAILED',
          Sent_At: '',
          Attachment: upper_(sub.PDF_Attach) === 'YES' ? issue.PDF_URL : '',
          Error: String(err),
          Version: issue.Version || payload.version || ''
        });
      }
    });

    const status = deliveryStatus_(eligible.length, sent + alreadySent, failed);
    setIssueFields_(issueSheet, ctx.row, {
      Email_Status: status,
      Email_Sent_At: status === 'SENT' ? new Date() : '',
      Email_Attachment: issue.PDF_URL,
      Email_Error: errors.join(' | ')
    });
    appendRunLog_(
      'EMAIL_DELIVERY',
      failed ? 'ERROR' : 'PASS',
      issue.Issue_ID,
      `eligible=${eligible.length}; sent_now=${sent}; already_sent=${alreadySent}; failed=${failed}`,
      payloadUrl
    );
  });
}

function buildMailOptions_(issue, payload, subscriber) {
  const kind = upper_(payload.kind || issue.Language);
  const html = buildEmailHtml_(issue, payload, subscriber);
  const options = {
    to: String(subscriber.Email).trim(),
    subject: emailSubject_(kind, payload.headline || issue.Headline),
    htmlBody: html,
    body: stripHtml_(html),
    name: 'Student News'
  };

  if (upper_(subscriber.PDF_Attach) === 'YES') {
    const response = UrlFetchApp.fetch(issue.PDF_URL, {muteHttpExceptions: true});
    if (response.getResponseCode() !== 200) {
      throw new Error('PDF attachment fetch failed: HTTP ' + response.getResponseCode());
    }
    const blob = response.getBlob().setName(
      safeFilename_(issue.Issue_ID || 'student-news') + '.pdf'
    );
    options.attachments = [blob];
  }
  return options;
}

function buildEmailHtml_(issue, payload, subscriber) {
  const kind = upper_(payload.kind || issue.Language);
  const name = esc_(subscriber.Name || '');
  const headline = esc_(payload.headline || issue.Headline || '');
  const fullUrl = escAttr_(issue.HTML_URL);
  const date = esc_(payload.date || issue.Publish_Date || '');
  const version = esc_(payload.version || issue.Version || '');
  let body = `<div style="font-family:Arial,'Noto Sans TC',sans-serif;line-height:1.6;max-width:680px;margin:auto">`;
  if (name) body += `<p>${name}，你好：</p>`;
  body += `<h1 style="font-size:24px;line-height:1.25">${headline}</h1>`;

  if (kind === 'ZH') {
    body += `<h2>30 秒先懂</h2><p>${esc_(payload.quick_start || '')}</p>`;
    body += `<h2>今天只記一件事</h2><p>${esc_(payload.one_thing || '')}</p>`;
    body += `<h2>1 個小問題</h2><p>${esc_(payload.mini_check || '')}</p>`;
  } else if (kind === 'EN') {
    body += `<h2>Quick Start</h2><p>${esc_(payload.quick_start || '')}</p>`;
    body += `<h2>5 Words</h2><p>${(payload.words || []).slice(0,5).map(esc_).join(' · ')}</p>`;
    body += `<h2>Focus Sentence</h2><p>${esc_(payload.focus_sentence || '')}</p>`;
    body += `<h2>1 Mini Check</h2><p>${esc_(payload.mini_check || '')}</p>`;
  } else {
    body += `<h2>本週 3–5 件事</h2><ul>`;
    (payload.events || []).slice(0,5).forEach(x => {
      body += `<li><b>${esc_(x.title || '')}</b> ${esc_(x.memory || '')}</li>`;
    });
    body += `</ul><h2>3 個概念</h2><p>${(payload.concepts || []).slice(0,3).map(esc_).join(' · ')}</p>`;
    body += `<h2>1–2 個英文詞</h2><p>${(payload.english_words || []).slice(0,2).map(esc_).join(' · ')}</p>`;
    const connection = payload.connection || {};
    body += `<h2>跨新聞連結</h2><p><b>${esc_(connection.title || '')}</b><br>${esc_(connection.question || '')}</p>`;
    body += `<h2>這週我最好奇什麼</h2><p>${esc_(payload.curiosity_prompt || '')}</p>`;
  }

  body += `<p style="margin:24px 0"><a href="${fullUrl}" style="background:#174f78;color:white;text-decoration:none;padding:12px 16px;border-radius:8px;display:inline-block">${kind === 'EN' ? 'Read Full Lesson' : '閱讀完整版'}</a></p>`;
  body += sourcesHtml_(payload.sources || []);
  body += `<p style="color:#667;font-size:13px">${date} · Version ${version}</p>`;
  body += `</div>`;
  return body;
}

function sourcesHtml_(sources) {
  if (!sources || !sources.length) return '';
  let out = '<h2>Sources</h2><ul>';
  sources.slice(0,3).forEach(s => {
    const title = esc_(s.title || '');
    const pub = esc_(s.publisher || '');
    const date = esc_(s.date || '');
    const url = isHttp_(s.url) ? escAttr_(s.url) : '';
    out += `<li>${pub} ${date} — ${url ? `<a href="${url}">${title}</a>` : title}</li>`;
  });
  return out + '</ul>';
}

function emailSubject_(kind, headline) {
  if (kind === 'EN') return '[Student News] ' + headline;
  if (kind === 'REVIEW') return '【Student News 週回顧】' + headline;
  return '【Student News】' + headline;
}

function shouldReceive_(subscriber, language) {
  if (upper_(subscriber.Active) !== 'YES') return false;
  const lang = upper_(language);
  if (lang === 'ZH') return upper_(subscriber.Receive_ZH) === 'YES';
  if (lang === 'EN') return upper_(subscriber.Receive_EN) === 'YES';
  if (lang === 'REVIEW') return upper_(subscriber.Receive_Sunday) === 'YES';
  return false;
}

function deliveryStatus_(eligible, sent, failed) {
  if (eligible === 0) return 'NO_RECIPIENTS';
  if (failed === 0) return 'SENT';
  if (sent > 0) return 'PARTIAL';
  return 'FAILED';
}

function emailKey_(issueId, recipient) {
  return String(issueId || '').trim() + '|' + String(recipient || '').trim().toLowerCase();
}

function emailAlreadySent_(logSheet, key) {
  const rows = records_(logSheet);
  return rows.some(ctx =>
    String(ctx.record.Delivery_Key || '') === key &&
    upper_(ctx.record.Status) === 'SENT'
  );
}

function appendEmailLog_(sheet, values) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  sheet.appendRow(headers.map(h => values[h] !== undefined ? values[h] : ''));
}

function appendRunLog_(stage, status, issueId, message, artifact) {
  const sheet = mustSheet_(SN.RUN_LOG);
  sheet.appendRow([
    new Date(),
    'gas-' + Utilities.getUuid().slice(0, 12),
    issueId,
    stage,
    status,
    0,
    '',
    message || '',
    artifact || ''
  ]);
}

function assertReadyForApproval_(issue) {
  if (upper_(issue.Status) !== 'READY') throw new Error('Status 必須是 READY。');
  ['Fact_QA', 'Teaching_QA', 'Layout_QA'].forEach(k => {
    if (upper_(issue[k]) !== 'PASS') throw new Error(k + ' 必須是 PASS。');
  });
}

function findTodayIssue_() {
  const sheet = mustSheet_(SN.ISSUES);
  const tz = automationValue_('TIMEZONE') || 'Asia/Taipei';
  const today = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  return records_(sheet).find(ctx => String(ctx.record.Publish_Date || '') === today) || null;
}

function selectedOrTodayIssue_() {
  const ss = SpreadsheetApp.getActive();
  const active = ss.getActiveSheet();
  if (active && active.getName() === SN.ISSUES && active.getActiveRange().getRow() > 1) {
    const row = active.getActiveRange().getRow();
    const headers = active.getRange(1, 1, 1, active.getLastColumn()).getValues()[0];
    const values = active.getRange(row, 1, 1, active.getLastColumn()).getValues()[0];
    return {sheet: active, row: row, record: objectFrom_(headers, values)};
  }
  return findTodayIssue_();
}

function setIssueFields_(sheet, row, updates) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const index = {};
  headers.forEach((h, i) => index[String(h)] = i + 1);
  Object.keys(updates).forEach(key => {
    if (index[key]) sheet.getRange(row, index[key]).setValue(updates[key]);
  });
}

function automationValue_(key) {
  const sheet = mustSheet_(SN.AUTOMATION);
  const values = sheet.getDataRange().getValues();
  for (let i = 3; i < values.length; i++) {
    if (String(values[i][0] || '').trim() === key) return values[i][1];
  }
  return '';
}

function triggerAutomation_() {
  const props = PropertiesService.getScriptProperties();
  const owner = props.getProperty('GITHUB_OWNER');
  const repo = props.getProperty('GITHUB_REPO');
  const token = props.getProperty('GITHUB_TOKEN');
  const workflow = props.getProperty('GITHUB_WORKFLOW') || 'daily.yml';
  const ref = props.getProperty('GITHUB_REF') || 'main';
  if (!owner || !repo || !token) return false;

  const url = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`;
  const res = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    payload: JSON.stringify({ref: ref}),
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json'
    }
  });
  const code = res.getResponseCode();
  if (code !== 204) throw new Error('GitHub workflow dispatch failed: HTTP ' + code + ' ' + res.getContentText());
  return true;
}

function fetchJson_(url) {
  const response = UrlFetchApp.fetch(url, {muteHttpExceptions: true});
  if (response.getResponseCode() !== 200) {
    throw new Error('Fetch email payload failed: HTTP ' + response.getResponseCode());
  }
  return JSON.parse(response.getContentText());
}

function records_(sheet) {
  const values = sheet.getDataRange().getValues();
  if (!values.length) return [];
  const headers = values[0].map(String);
  const rows = [];
  for (let r = 1; r < values.length; r++) {
    if (values[r].every(v => v === '')) continue;
    rows.push({sheet: sheet, row: r + 1, record: objectFrom_(headers, values[r])});
  }
  return rows;
}

function objectFrom_(headers, values) {
  const out = {};
  headers.forEach((h, i) => out[h] = values[i]);
  return out;
}

function mustSheet_(name) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(name);
  if (!sheet) throw new Error('Missing sheet: ' + name);
  return sheet;
}

function upper_(value) {
  return String(value || '').trim().toUpperCase();
}

function isHttp_(value) {
  return /^https?:\/\//i.test(String(value || '').trim());
}

function esc_(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escAttr_(value) {
  return esc_(value);
}

function stripHtml_(value) {
  return String(value || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

function safeFilename_(value) {
  return String(value || '').replace(/[^A-Za-z0-9._-]+/g, '-');
}
