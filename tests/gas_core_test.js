const fs = require('fs');
const vm = require('vm');
const path = require('path');

const code = fs.readFileSync(path.join(__dirname, '..', 'gas', 'Code.gs'), 'utf8');
vm.runInThisContext(code);

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const parent = {
  Active:'YES', Receive_ZH:'YES', Receive_EN:'YES', Receive_Sunday:'YES', PDF_Attach:'YES'
};
const student = {
  Active:'YES', Receive_ZH:'NO', Receive_EN:'YES', Receive_Sunday:'YES', PDF_Attach:'YES'
};
const off = {
  Active:'NO', Receive_ZH:'YES', Receive_EN:'YES', Receive_Sunday:'YES'
};

assert(shouldReceive_(parent, 'ZH') === true, 'parent should receive ZH');
assert(shouldReceive_(student, 'ZH') === false, 'student should not receive ZH');
assert(shouldReceive_(student, 'EN') === true, 'student should receive EN');
assert(shouldReceive_(student, 'REVIEW') === true, 'student should receive Sunday');
assert(shouldReceive_(off, 'EN') === false, 'inactive should receive nothing');

assert(emailKey_('ISSUE-1', 'Parent@Example.com') === 'ISSUE-1|parent@example.com', 'idempotency key');
assert(deliveryStatus_(2,2,0) === 'SENT', 'sent status');
assert(deliveryStatus_(2,1,1) === 'PARTIAL', 'partial status');
assert(deliveryStatus_(2,0,2) === 'FAILED', 'failed status');
assert(deliveryStatus_(0,0,0) === 'NO_RECIPIENTS', 'no recipient status');

assert(code.includes('MailApp.sendEmail'), 'MailApp delivery missing');
assert(code.includes('UrlFetchApp.fetch(issue.PDF_URL'), 'PDF attachment fetch missing');
assert(code.includes("upper_(issue.Status) !== 'PUBLISHED'"), 'email publication gate missing');
assert(code.includes('appendRunLog_'), 'RUN_LOG evidence missing');


// EMAIL_LOG idempotency: already-SENT key must be skipped.
const originalRecords = records_;
records_ = function(_sheet) {
  return [{ record: { Delivery_Key:'ISSUE-1|parent@example.com', Status:'SENT' } }];
};
assert(emailAlreadySent_({}, 'ISSUE-1|parent@example.com') === true, 'already-sent key should be idempotent');
assert(emailAlreadySent_({}, 'ISSUE-1|other@example.com') === false, 'different recipient should not be skipped');
records_ = originalRecords;

assert(code.includes('function retryFailedEmails()'), 'failed-email retry action missing');
assert(code.includes("deliverEmails_(['FAILED', 'PARTIAL'])"), 'retry must target only failed/partial email states');

// Email delivery must never rewrite article publication status.
const deliveryStart = code.indexOf('function deliverEmails_(');
const deliveryEnd = code.indexOf('function buildEmail_', deliveryStart);
const deliveryBody = code.slice(deliveryStart, deliveryEnd);
assert(!/setIssueField_\([^\\n]*['"]Status['"]/.test(deliveryBody), 'email delivery must not roll back article Status');

console.log('GAS core tests: PASS');
