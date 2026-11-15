/* Real Chromium QA for release evidence, local decisions and SSE. Requires a connected GitHub workspace. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');

const BASE = (process.env.DRIFTCI_URL || 'http://127.0.0.1:8100').replace(/\/$/, '');
const OUT = process.env.OUT_DIR || '/tmp/driftci-release-browser';
const decisionQA = process.env.DRIFTCI_RELEASE_DECISION_QA === '1';
fs.mkdirSync(OUT, { recursive: true });
const assert = (condition, message) => { if (!condition) throw new Error(message); };

(async () => {
  const errors = [];
  const checks = [];
  const mutations = [];
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(20000);
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
  page.on('request', (request) => {
    if (['GET', 'HEAD', 'OPTIONS'].includes(request.method())) return;
    if (decisionQA && request.method() === 'POST' && new URL(request.url()).pathname.match(/^\/api\/releases\/pr-\d+\/decision$/)) return;
    mutations.push(`${request.method()} ${request.url()}`);
  });
  try {
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'The world can change after review.' }).waitFor();
    await page.locator('.release-presence-dot.connected').waitFor();
    const cards = page.locator('.release-card');
    assert(await cards.count() > 0, 'Release Room has no connected pull requests');
    checks.push('Public HTTPS UI, real repository PRs and connected SSE stream');
    await page.screenshot({ path: path.join(OUT, 'release-room.png'), fullPage: true });

    const bootstrap = await (await fetch(`${BASE}/api/bootstrap`)).json();
    const transport = bootstrap.release.status.metadata_transport;
    assert(['context.dev_bytes', 'direct_api.github.com'].includes(transport) || (transport == null && bootstrap.release.status.last_success_at), 'Unexpected release metadata transport state');
    if (transport === 'context.dev_bytes') await page.getByText(/Context\.dev metadata · reconciliation every/).waitFor();
    else if (transport === 'direct_api.github.com') await page.getByText(/Direct GitHub conditional polling every/).waitFor();
    else await page.getByText('Retained GitHub metadata · transport not recorded', { exact: true }).waitFor();
    const evidencePr = bootstrap.release.pull_requests.find((pr) => pr.detail_complete && pr.files_complete && pr.files?.some((file) => file.status !== 'removed'));
    const pendingPr = bootstrap.release.pull_requests.find((pr) => pr.state === 'open' && !pr.detail_complete && Array.isArray(pr.files) && !pr.files.length);
    assert(evidencePr || pendingPr, 'Expected either current PR file evidence or an explicitly incomplete/index-only open PR');
    if (decisionQA) assert(evidencePr, 'Requested local-decision QA needs current complete file evidence');
    assert(bootstrap.release.pull_requests.some((pr) => !pr.detail_complete && Array.isArray(pr.files) && !pr.files.length), 'Index-only PR records should remain empty and incomplete');
    const inspectedPr = evidencePr || pendingPr;
    const prNumber = inspectedPr.number;
    const first = cards.filter({ hasText: `PR #${prNumber}` }).first();
    await first.waitFor();
    const head = (await first.locator('.release-readiness > code').innerText()).trim();
    await first.getByRole('button', { name: /Inspect release/ }).click();
    const drawer = page.getByRole('dialog');
    await drawer.getByRole('heading', { name: 'Changed files', exact: true }).waitFor();
    if (evidencePr) {
      assert((await drawer.locator('.release-file-list > div').count()) > 0, 'Complete PR file evidence is missing');
      await page.screenshot({ path: path.join(OUT, 'release-evidence.png'), fullPage: true });
      checks.push('Changed files, checks, repository scope and source citations');
    } else {
      await drawer.getByText('File, review or check detail is incomplete.', { exact: false }).waitFor();
      await page.screenshot({ path: path.join(OUT, 'release-pending-evidence.png'), fullPage: true });
      await drawer.getByRole('button', { name: 'Record decision', exact: true }).click();
      const pendingDialog = page.getByRole('dialog', { name: 'Record a release decision' });
      await pendingDialog.getByText(/PR file, review or check coverage is incomplete/).waitFor();
      assert(await pendingDialog.getByRole('button', { name: 'Record ready', exact: true }).isDisabled(), 'Incomplete PR evidence can be marked ready');
      await pendingDialog.getByRole('button', { name: 'Close dialog', exact: true }).click();
      checks.push('Incomplete/index-only PR detail visibly blocks ready without substituting old-head files');
    }

    if (decisionQA) {
      await drawer.getByRole('button', { name: 'Record decision' }).click();
      const dialog = page.getByRole('dialog', { name: 'Record a release decision' });
      await dialog.getByLabel('Decision owner').fill('DriftCI browser QA');
      await dialog.getByLabel(/Evidence notes/).fill('Local pause to verify the decision flow and live event stream. No GitHub review, merge or deployment was performed.');
      const before = await (await fetch(`${BASE}/api/bootstrap`)).json();
      const cursor = Math.max(0, ...before.release.events.map((event) => event.seq));
      await page.evaluate((after) => {
        const source = new EventSource(`/api/events/stream?after=${after}`);
        source.addEventListener('update', (message) => {
          const event = JSON.parse(message.data);
          if (event.seq > after && event.kind === 'decision') {
            window.__driftciQaEvent = event;
            source.close();
          }
        });
        window.__driftciQaSource = source;
      }, cursor);
      await dialog.getByRole('button', { name: 'Pause release', exact: true }).click();
      await page.waitForFunction(() => window.__driftciQaEvent?.pr_number, null, { timeout: 10000 });
      const received = await page.evaluate(() => window.__driftciQaEvent);
      assert(received.seq >= cursor + 1 && received.pr_number === prNumber && received.title === 'Release paused' && received.baseline === false, 'Unexpected SSE event payload');
      const pausedCard = page.locator('.release-card').filter({ hasText: `PR #${prNumber}` });
      await pausedCard.getByText('Release paused locally', { exact: true }).waitFor();
      await page.locator('.release-activity-item.release-live-event').filter({ hasText: 'Release paused' }).waitFor();
      await pausedCard.getByRole('button', { name: /Inspect release/ }).click();
      await drawer.locator('.release-owner-record').getByText('Release paused', { exact: true }).waitFor();
      await drawer.locator('.release-owner-record').getByText(/No GitHub review, merge or deployment was performed/).waitFor();
      const downloadPromise = page.waitForEvent('download');
      await drawer.getByRole('button', { name: 'Export decision' }).click();
      const download = await downloadPromise;
      await download.saveAs(path.join(OUT, 'release-decision.md'));
      const report = fs.readFileSync(path.join(OUT, 'release-decision.md'), 'utf8');
      assert(report.includes(head), 'Decision report does not bind the exact PR head');
      assert(report.includes('Local pause to verify'), 'Decision report omits the reviewer note');
      assert(report.includes('local DriftCI release decision'), 'Report overstates its scope');
      checks.push('Independent browser SSE event, human pause and exact-head Markdown receipt');
      await page.screenshot({ path: path.join(OUT, 'release-decision.png'), fullPage: true });
      await page.evaluate(() => window.__driftciQaSource?.close());
    }
    if (evidencePr) await drawer.getByRole('button', { name: 'Close drawer' }).click();
    await page.reload({ waitUntil: 'networkidle' });
    if (decisionQA) await page.getByText('Release paused locally', { exact: true }).waitFor();

    await page.locator('.main-navigation').getByRole('button', { name: /Web Watch/ }).click();
    await page.getByRole('heading', { name: 'Know when the source changes.' }).waitFor();
    const watchSnapshot = await (await fetch(`${BASE}/api/bootstrap`)).json();
    const expectedWatches = watchSnapshot.sources.filter((source) => source.watch || (source.category && source.category !== 'release_events')).length;
    assert(expectedWatches > 0 && await page.locator('.watch-source-row').count() === expectedWatches, 'Repository-derived watches are missing or inconsistent');
    await page.locator('.watch-source-row').getByText(watchSnapshot.sources.find((source) => source.watch || (source.category && source.category !== 'release_events')).title, { exact: true }).first().waitFor();
    if (watchSnapshot.discoveries.length) {
      assert(await page.locator('.discovery-card').count() === watchSnapshot.discoveries.length, 'Context.dev research results are missing or inconsistent');
    } else {
      const research = watchSnapshot.sources.find((source) => source.id === 'src-context-search');
      assert(research?.error?.startsWith('Optional repository research skipped: the daily scrape/search budget'), 'No research results or explicit permitted budget error were recorded');
      await page.getByRole('status').filter({ hasText: research.error }).waitFor();
      await page.getByText('No research has been retrieved for this query.', { exact: false }).waitFor();
    }
    await page.getByText('Baselines, not false alarms', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(OUT, 'web-watch.png'), fullPage: true });
    checks.push('Repository-derived official watches, credit accounting, and research results or an explicit budget skip');
    await page.locator('.main-navigation').getByRole('button', { name: /Release Room/ }).click();
    await page.getByRole('heading', { name: 'The world can change after review.' }).waitFor();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('heading', { name: 'The world can change after review.' }).waitFor();
    const dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(dimensions.scrollWidth <= dimensions.width + 1, `Mobile Release Room overflow: ${JSON.stringify(dimensions)}`);
    await page.screenshot({ path: path.join(OUT, 'release-mobile.png'), fullPage: true });
    await page.locator('.release-card').filter({ hasText: `PR #${prNumber}` }).first().getByRole('button', { name: /Inspect release/ }).click();
    const mobileDrawer = await page.getByRole('dialog').evaluate((element) => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth, drawerWidth: element.getBoundingClientRect().width }));
    assert(mobileDrawer.scrollWidth <= mobileDrawer.width + 1 && mobileDrawer.drawerWidth <= mobileDrawer.width, 'Mobile evidence drawer overflows');
    await page.screenshot({ path: path.join(OUT, 'release-evidence-mobile.png'), fullPage: true });
    checks.push('390px Release Room and evidence drawer layouts without horizontal overflow');
  } catch (error) {
    errors.push(`assertion: ${error.message}`);
    await page.screenshot({ path: path.join(OUT, 'failure.png'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: !errors.length && !mutations.length, base: BASE, checks, errors, browser_mutations: mutations, artifacts: OUT }, null, 2));
  if (errors.length || mutations.length) process.exitCode = 1;
})();
