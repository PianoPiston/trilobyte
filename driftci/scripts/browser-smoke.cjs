/* Real Chromium QA for the Context.dev watch, review and incident workflows. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');

const BASE = (process.env.DRIFTCI_URL || 'http://127.0.0.1:8100').replace(/\/$/, '');
const OUT = process.env.OUT_DIR || '/tmp/driftci-browser';
const keepWorkspace = process.env.DRIFTCI_KEEP_WORKSPACE === '1';
const executablePath = process.env.CHROMIUM_EXECUTABLE || '~/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome';
fs.mkdirSync(OUT, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
async function capture(page, name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: true });
}
async function api(pathname, method = 'GET') {
  let response;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    response = await fetch(`${BASE}/api${pathname}`, { method });
    if (response.status !== 429 || pathname !== '/scan') break;
    const retryAfter = Math.max(1, Number(response.headers.get('retry-after')) || 3);
    await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000));
  }
  assert(response.ok, `${method} ${pathname} failed: ${response.status}`);
  return response.json();
}

(async () => {
  const errors = [];
  const checks = [];
  const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(20000);
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()} ${message.location().url || ''}`); });

  try {
    await api('/demo/reset', 'POST');
    await api('/scan', 'POST'); // Uses the six-hour cache when present; never forces extra credits.
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Live changes. Exact blast radius.' }).waitFor();
    assert((await page.title()).includes('DriftCI'), 'Document title is not branded');
    assert(await page.getByText('Live web memory · Context.dev', { exact: true }).count() > 0, 'Context.dev pulse is missing');
    assert(await page.getByRole('button', { name: /generate|review patch|export patch/i }).count() === 0, 'Patch-generation actions are still visible');
    checks.push('Mission control with live web pulse and cached live-source refresh');
    await capture(page, 'overview.png');

    await page.locator('.decision-item').filter({ hasText: 'gpt-4-0314' }).first().click();
    await page.getByRole('heading', { name: 'A retired model is still configured' }).waitFor();
    await page.getByText('Source-to-code evidence').waitFor();
    assert(await page.getByText('src/lib/ai.ts', { exact: false }).count() > 0, 'Summary source evidence missing');
    assert(await page.getByText('src/jobs/escalation.ts', { exact: false }).count() > 0, 'Escalation source evidence missing');
    await page.getByRole('button', { name: 'Mark reviewed' }).click();
    await page.getByText('Acknowledged', { exact: true }).first().waitFor();
    await capture(page, 'change-review.png');
    await page.getByRole('button', { name: 'Close drawer' }).click();
    checks.push('Signal evidence and persisted human review; no patch actions');

    await page.locator('.main-navigation').getByRole('button', { name: /Web Watch/ }).click();
    await page.getByRole('heading', { name: 'Know when the source changes.' }).waitFor();
    assert(await page.locator('.watch-source-row').count() >= 5, 'Repository-derived watches are missing');
    assert(await page.locator('.discovery-card').count() > 0, 'Context.dev research results are missing');
    assert(await page.getByText('Baselines, not false alarms', { exact: true }).count() > 0, 'Initial-baseline behavior is not explained');
    await page.locator('#root').getByText('Context.dev web intelligence', { exact: true }).waitFor();
    await capture(page, 'web-watch.png');
    checks.push('Five live watches, Context.dev budget and scoped research receipts');

    await page.locator('.main-navigation').getByRole('button', { name: /Change Inbox/ }).click();
    await page.getByRole('heading', { name: 'Follow the signal to the source.' }).waitFor();
    await page.getByPlaceholder('Search provider, CVE or affected asset').fill('gpt-4-0314');
    assert(await page.locator('.signal-row').count() >= 1, 'Change search returned no model signal');
    assert(await page.getByRole('button', { name: /generate patch/i }).count() === 0, 'Patch action returned in Change Inbox');
    await capture(page, 'change-inbox.png');
    checks.push('Searchable change inbox without patch generation');

    await page.locator('.main-navigation').getByRole('button', { name: /Vulnerabilities/ }).click();
    await page.getByRole('heading', { name: 'Work the incident, not just the CVE.' }).waitFor();
    await page.getByText('CVE-2025-29927', { exact: true }).first().waitFor();
    await capture(page, 'vulnerabilities.png');
    const contain = page.getByRole('button', { name: 'Complete: Contain exposure' });
    if (await contain.count()) {
      await contain.click();
      await page.getByRole('button', { name: 'Reopen: Contain exposure' }).waitFor();
    }
    const reportDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export IR record' }).click();
    const reportDownload = await reportDownloadPromise;
    await reportDownload.saveAs(path.join(OUT, 'cve-incident.md'));
    const incidentReport = fs.readFileSync(path.join(OUT, 'cve-incident.md'), 'utf8');
    assert(incidentReport.includes('GHSA-f82v-jwr5-mffw'), 'IR report lacks canonical advisory evidence');
    await page.getByRole('tab', { name: /CVE history/ }).click();
    await page.getByText('CVE-2024-34351', { exact: true }).waitFor();
    checks.push('CVE evidence, response checklist, IR export and history');

    await page.route('**/api/bootstrap', async (route) => {
      const response = await route.fetch();
      const payload = await response.json();
      const osv = payload.sources.find((source) => source.publisher === 'OSV');
      if (osv) Object.assign(osv, { status: 'partial', packages_total: 76, packages_checked: 32, packages_pending: 44 });
      payload.workspace = {
        ...payload.workspace,
        name: 'Large public repository', repository: 'acme/large-repository', source: 'github',
        coverage: {
          mode: 'github_tree_selective', archive_downloaded: false, commit_sha: 'a'.repeat(40),
          complete: false, tree_truncated: true, repository_files: 95000,
          candidate_files: 21, selected_files: 10, files_read: 10,
          skipped_large_files: 1, skipped_budget_files: 9, failed_files: 1, timed_out_files: 1,
          bytes_read: 82000, file_limit: 120, byte_limit: 4000000,
          per_file_limit: 1000000, repository_size_kb: 90000,
          source_read_seconds: 1.6, time_budget_seconds: 25, per_file_timeout_seconds: 6,
        },
      };
      await route.fulfill({ response, json: payload });
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.getByTestId('partial-osv-notice').waitFor();
    await page.getByRole('button', { name: 'Repository and demo controls' }).click();
    await page.getByTestId('repository-coverage').waitFor();
    const coverageText = await page.getByTestId('repository-coverage').innerText();
    assert(coverageText.includes('10 / 21') && coverageText.includes('No archive or clone'), 'Selective source coverage is incomplete');
    assert((await page.locator('#repository-help').innerText()).includes('120 files / 4 MB'), 'Updated source bounds are absent');
    await capture(page, 'repository-coverage.png');
    await page.getByRole('button', { name: 'Close drawer' }).click();
    await page.unroute('**/api/bootstrap');
    checks.push('Selective 120-file source budget and partial-result disclosure');

    await page.reload({ waitUntil: 'networkidle' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('heading', { name: 'Live changes. Exact blast radius.' }).waitFor();
    let dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(dimensions.scrollWidth <= dimensions.width + 1, `Mobile overview overflows: ${JSON.stringify(dimensions)}`);
    await capture(page, 'mobile.png');
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await page.locator('.main-navigation').getByRole('button', { name: /Web Watch/ }).click();
    await page.getByRole('heading', { name: 'Know when the source changes.' }).waitFor();
    dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(dimensions.scrollWidth <= dimensions.width + 1, `Mobile watch view overflows: ${JSON.stringify(dimensions)}`);
    await capture(page, 'web-watch-mobile.png');
    checks.push('390px Mission Control and Web Watch layouts without horizontal overflow');
  } catch (error) {
    await capture(page, 'failure.png').catch(() => {});
    errors.push(`assertion: ${error.message}`);
  } finally {
    if (!keepWorkspace) await api('/demo/reset', 'POST').catch(() => {});
    await browser.close();
  }

  const report = { ok: errors.length === 0, base: BASE, checks, errors, artifacts: OUT };
  console.log(JSON.stringify(report, null, 2));
  if (errors.length) process.exitCode = 1;
})();
