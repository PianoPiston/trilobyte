/* Real Chromium workflow test. Requires playwright-core and an executable Chromium.
 * Local example:
 *   npm install --prefix /tmp/driftci-browser playwright-core
 *   PLAYWRIGHT_MODULE=/tmp/driftci-browser/node_modules/playwright-core \
 *   CHROMIUM_EXECUTABLE=$HOME/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome \
 *   node scripts/browser-smoke.cjs
 * The application must already be running. OUT_DIR receives screenshots and patch export.
 */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');

const BASE = (process.env.DRIFTCI_URL || 'http://127.0.0.1:8100').replace(/\/$/, '');
const OUT = process.env.OUT_DIR || '/tmp/driftci-browser';
const repository = process.env.DRIFTCI_REPOSITORY || '';
const keepWorkspace = process.env.DRIFTCI_KEEP_WORKSPACE === '1' && Boolean(repository);
let repositoryTest = null;
const executablePath = process.env.CHROMIUM_EXECUTABLE || '~/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome';
fs.mkdirSync(OUT, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
async function capture(page, name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: true });
}

(async () => {
  const errors = [];
  const checks = [];
  const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(15000);
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()} ${message.location().url || ''}`); });

  try {
    await fetch(`${BASE}/api/demo/reset`, { method: 'POST' }).then((response) => { assert(response.ok, `Initial reset failed: ${response.status}`); });
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Changes that need a decision.' }).waitFor();
    assert((await page.title()).includes('DriftCI'), 'Document title is not branded');
    assert(await page.getByText('gpt-4-0314', { exact: false }).count() > 0, 'Model evidence is not visible');
    checks.push('Mission control and live API bootstrap');
    await capture(page, 'overview.png');

    await page.getByRole('button', { name: /A retired model is still configured/i }).first().click();
    await page.getByRole('heading', { name: 'A retired model is still configured' }).waitFor();
    await page.getByText('Source-to-code evidence').waitFor();
    assert(await page.getByText('src/lib/ai.ts', { exact: false }).count() > 0, 'Summary source evidence missing');
    assert(await page.getByText('src/jobs/escalation.ts', { exact: false }).count() > 0, 'Escalation source evidence missing');
    assert(await page.getByText('Historical replay', { exact: true }).count() > 0, 'Replay provenance not labelled');
    checks.push('Signal drawer with two exact source locations and provenance');

    await page.getByRole('button', { name: 'Generate targeted fix' }).click();
    await page.getByRole('heading', { name: 'Review remediation' }).waitFor();
    assert(await page.getByRole('button', { name: 'Export patch' }).isDisabled(), 'Patch export should require approval');
    assert(await page.getByText('Retired identifier removed').count() > 0, 'Static model check missing');
    assert(await page.getByText('Repository tests', { exact: true }).count() > 0, 'Pending repository test disclosure missing');
    await page.getByRole('tab', { name: /src\/jobs\/escalation\.ts/ }).click();
    assert((await page.locator('.diff-code').innerText()).includes('gpt-4.1'), 'Rendered diff does not include the replacement');
    await capture(page, 'model-fix.png');
    await page.getByRole('button', { name: 'Approve remediation' }).click();
    await page.getByText(/Approved /).waitFor();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export patch' }).click();
    const download = await downloadPromise;
    await download.saveAs(path.join(OUT, 'model.patch'));
    const patch = fs.readFileSync(path.join(OUT, 'model.patch'), 'utf8');
    assert(patch.includes('--- a/src/lib/ai.ts'), 'Patch lacks summary file');
    assert(patch.includes('--- a/src/jobs/escalation.ts'), 'Patch lacks escalation file');
    assert(patch.includes('-export const SUMMARY_MODEL = "gpt-4-0314" as const;'), 'Patch does not remove the retired model');
    assert(patch.includes('+export const SUMMARY_MODEL = "gpt-4.1" as const;'), 'Patch lacks the replacement');
    checks.push('Two-file unified diff, approval gate and actual patch download');
    await page.getByRole('button', { name: 'Close dialog' }).click();
    await page.getByRole('button', { name: 'Close drawer' }).click();

    await page.getByRole('button', { name: /Vulnerabilities/ }).click();
    await page.getByRole('heading', { name: 'Work the incident, not just the CVE.' }).waitFor();
    await page.getByText('CVE-2025-29927', { exact: true }).first().waitFor();
    await capture(page, 'vulnerabilities.png');
    await page.getByRole('button', { name: 'Complete: Contain exposure' }).click();
    await page.getByRole('button', { name: 'Reopen: Contain exposure' }).waitFor();
    const reportDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export IR record' }).click();
    const reportDownload = await reportDownloadPromise;
    await reportDownload.saveAs(path.join(OUT, 'cve-incident.md'));
    const incidentReport = fs.readFileSync(path.join(OUT, 'cve-incident.md'), 'utf8');
    assert(incidentReport.includes('| Contain exposure | done |'), 'IR report lacks the completed response step');
    assert(incidentReport.includes('GHSA-f82v-jwr5-mffw'), 'IR report lacks canonical advisory evidence');
    checks.push('CVE incident evidence, persisted checklist transition and IR report export');

    await page.getByRole('tab', { name: /CVE history/ }).click();
    await page.getByText('CVE-2024-34351', { exact: true }).waitFor();
    await capture(page, 'vulnerability-history.png');
    checks.push('Resolved vulnerability history');

    await fetch(`${BASE}/api/demo/reset`, { method: 'POST' }).then((response) => { assert(response.ok, `Final reset failed: ${response.status}`); });
    await page.route('**/api/bootstrap', async (route) => {
      const response = await route.fetch();
      const payload = await response.json();
      const osv = payload.sources.find((source) => source.publisher === 'OSV');
      if (osv) Object.assign(osv, { status: 'partial', packages_total: 76, packages_checked: 32, packages_pending: 44 });
      payload.workspace = {
        ...payload.workspace,
        name: 'Large public repository',
        repository: 'acme/large-repository',
        source: 'github',
        coverage: {
          mode: 'github_tree_selective', archive_downloaded: false,
          commit_sha: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          complete: false, tree_truncated: true, repository_files: 95000,
          candidate_files: 21, selected_files: 10, files_read: 10,
          skipped_large_files: 1, skipped_budget_files: 9, failed_files: 1, timed_out_files: 1,
          bytes_read: 82000, file_limit: 64, byte_limit: 2000000,
          per_file_limit: 1000000, repository_size_kb: 90000,
          source_read_seconds: 1.6, time_budget_seconds: 25, per_file_timeout_seconds: 6,
        },
      };
      await route.fulfill({ response, json: payload });
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.getByTestId('partial-scan-notice').waitFor();
    await page.getByTestId('partial-osv-notice').waitFor();
    assert((await page.getByTestId('partial-osv-notice').innerText()).includes('44 are pending'), 'OSV package budget is not disclosed');
    await page.getByRole('button', { name: 'Repository and demo controls' }).click();
    await page.getByTestId('repository-coverage').waitFor();
    const coverageText = await page.getByTestId('repository-coverage').innerText();
    assert(coverageText.includes('10 / 21'), 'Selective repository read counts are absent');
    assert(coverageText.includes('No archive or clone'), 'No-archive reader explanation is absent');
    assert((await page.locator('#repository-help').innerText()).includes('64 files / 2 MB'), 'Bounded loading-time explanation is absent');
    assert(coverageText.includes('not evidence of absence'), 'Partial-coverage warning is absent');
    assert(coverageText.includes('aaaaaaaaaaaa'), 'Pinned source commit is absent');
    assert(coverageText.includes('exceeded the time budget'), 'Timeout accounting is not shown');
    await capture(page, 'repository-coverage.png');
    checks.push('Large-repository selective reader coverage and partial-result disclosure');
    await page.getByRole('button', { name: 'Close drawer' }).click();
    await page.unroute('**/api/bootstrap');
    await page.reload({ waitUntil: 'networkidle' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('heading', { name: 'Changes that need a decision.' }).waitFor();
    const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(dimensions.scrollWidth <= dimensions.width + 1, `Mobile page overflows: ${JSON.stringify(dimensions)}`);
    await capture(page, 'mobile.png');
    assert(await page.getByRole('button', { name: 'Open navigation' }).isVisible(), 'Mobile navigation control is not available');
    checks.push('390px responsive layout without document overflow');

    if (repository) {
      await page.setViewportSize({ width: 1440, height: 1050 });
      await page.getByRole('button', { name: 'Repository and demo controls' }).click();
      await page.locator('#repository-url').fill(repository);
      await page.getByRole('button', { name: 'Connect & scan repository' }).click();
      await page.locator('.repository-progress').waitFor();
      const started = Date.now();
      await page.getByRole('button', { name: 'Close drawer' }).waitFor({ state: 'detached', timeout: 90000 });
      await page.getByTestId('partial-scan-notice').waitFor();
      const osvNotice = page.getByTestId('partial-osv-notice');
      if (await osvNotice.count()) assert((await osvNotice.innerText()).includes('pending'), 'OSV scope is not explained for the real repository');
      await page.getByRole('button', { name: 'Repository and demo controls' }).click();
      await page.getByTestId('repository-coverage').waitFor();
      const text = await page.getByTestId('repository-coverage').innerText();
      assert(text.includes('Partial coverage'), 'Large-repository index should be explicitly partial');
      assert(text.includes('No archive or clone'), 'Real connection used an unexpected archive path');
      assert(text.includes('file-read time'), 'Real connection did not report source-read timing');
      repositoryTest = { url: repository, elapsed_seconds: Math.round((Date.now() - started) / 100) / 10, kept_workspace: keepWorkspace };
      await capture(page, 'repository-live-connect.png');
      checks.push(`Real public UI connection to ${repository} completed in ${repositoryTest.elapsed_seconds}s with bounded/partial coverage`);
    }
  } catch (error) {
    await capture(page, 'failure.png').catch(() => {});
    errors.push(`assertion: ${error.message}`);
  } finally {
    if (!keepWorkspace) await fetch(`${BASE}/api/demo/reset`, { method: 'POST' }).catch(() => {});
    await browser.close();
  }

  const report = { ok: errors.length === 0, base: BASE, checks, repository_test: repositoryTest, errors, artifacts: OUT };
  console.log(JSON.stringify(report, null, 2));
  if (errors.length) process.exitCode = 1;
})();
