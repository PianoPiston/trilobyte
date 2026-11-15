/* Read-only Chromium QA for repository coverage, incident scope and hosted monitoring. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');

const BASE = (process.env.DRIFTCI_URL || 'http://127.0.0.1:8100').replace(/\/$/, '');
const OUT = process.env.OUT_DIR || '/tmp/driftci-coverage-browser';
fs.mkdirSync(OUT, { recursive: true });
const assert = (condition, message) => { if (!condition) throw new Error(message); };
(async () => {
  const checks = [];
  const errors = [];
  const mutations = [];
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(30000);
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
  page.on('request', (request) => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) mutations.push(`${request.method()} ${request.url()}`);
  });
  let report = {};
  try {
    const [data, health] = await Promise.all([
      fetch(`${BASE}/api/bootstrap`).then(async (response) => { assert(response.ok, `Bootstrap HTTP ${response.status}`); return response.json(); }),
      fetch(`${BASE}/api/health`).then(async (response) => { assert(response.ok, `Health HTTP ${response.status}`); return response.json(); }),
    ]);
    assert(data.workspace.source === 'github' && !/github\.com\//.test(data.workspace.repository), 'Expected a canonical connected repository');
    const coverage = data.workspace.coverage;
    assert(coverage && coverage.archive_downloaded === false, 'Pinned source coverage or archive denial is missing');
    assert(coverage.manifest_files_read === coverage.manifest_candidates, 'Not every discovered manifest was read');
    assert(!coverage.source_complete, 'Partial source coverage is incorrectly marked complete');
    assert(coverage.skipped_budget_files > 0 || coverage.skipped_large_files > 0, 'A complete source index needs a different fixture');
    const osv = data.sources.find((source) => source.id === 'src-osv');
    assert(osv && osv.packages_checked + osv.packages_pending === osv.packages_eligible, 'OSV eligibility and query coverage do not reconcile');
    assert(osv.advisory_details_retrieved + osv.advisory_details_pending === osv.advisory_details_requested, 'Advisory-detail accounting does not reconcile');
    assert(osv.complete === (osv.packages_pending === 0), 'OSV completion hides unsupported-query gaps');
    assert(typeof data.monitor?.id === 'string' && data.monitor.mode === 'remote_scheduled', 'A remote Context.dev monitor is required for this evidence check');
    const usage = health.context_dev.usage;
    assert(usage.daily_available >= 0 && usage.monitor_spent_and_reserved >= 0, 'Invalid local Context.dev budget accounting');
    checks.push('Canonical repository, bounded source coverage, reconciled advisory counts and real monitor metadata');

    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.locator('.release-presence-dot.connected').waitFor();
    await page.getByRole('button', { name: 'Repository and demo controls', exact: true }).click();
    const drawer = page.getByRole('dialog');
    const facts = drawer.getByTestId('repository-coverage');
    await facts.waitFor();
    assert((await facts.innerText()).includes(`${coverage.manifest_files_read} / ${coverage.manifest_candidates}`), 'Manifest read coverage is not rendered');
    assert((await facts.innerText()).includes('Context.dev’s byte-preserving request transport'), 'Metadata transport is not disclosed');
    await page.screenshot({ path: path.join(OUT, 'repository-coverage.png'), fullPage: true });
    const parseErrors = coverage.dependency_parse_errors || [];
    if (parseErrors.length) {
      await drawer.locator('.parse-error-list summary').click();
      assert(await drawer.locator('.parse-error-list > div').count() === parseErrors.length, 'Parse-failure details are incomplete');
      await drawer.locator('.parse-error-list > div').last().scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(OUT, 'manifest-parse-evidence.png'), fullPage: true });
    }
    await drawer.locator('.native-component-list summary').click();
    await drawer.locator('.native-component-list').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(OUT, 'native-declarations.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await drawer.locator('.native-component-list').scrollIntoViewIfNeeded();
    const mobile = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(mobile.scrollWidth <= mobile.width + 1, `Mobile coverage overflow: ${JSON.stringify(mobile)}`);
    await page.screenshot({ path: path.join(OUT, 'repository-coverage-mobile.png'), fullPage: true });
    checks.push('Real manifest/native evidence, transport disclosure and 390px long-path wrapping');
    await page.setViewportSize({ width: 1440, height: 1050 });
    await drawer.getByRole('button', { name: 'Close drawer', exact: true }).click();

    await page.locator('.main-navigation').getByRole('button', { name: /^Vulnerabilities/ }).click();
    await page.locator('.incident-facts').waitFor();
    const bundled = data.incidents.find((incident) => incident.dependency_scope === 'bundled');
    assert(bundled, 'Expected an actual bundled-scope incident');
    assert(bundled.manifest, 'The persisted incident omitted its evidence manifest');
    await page.locator('.incident-list-item').filter({ hasText: `${bundled.affected_package}@${bundled.affected_version}` }).first().click();
    await page.locator('.incident-facts').getByText('Bundled', { exact: true }).waitFor();
    await page.locator('.incident-facts').getByText(bundled.manifest, { exact: true }).waitFor();
    await page.getByText('Bundled inventory evidence. Review the owning component’s workflow and deployment separately.', { exact: false }).waitFor();
    await page.locator('.incident-detail').screenshot({ path: path.join(OUT, 'incident-scope.png') });
    const uniqueCves = new Set(data.signals.filter((signal) => signal.kind === 'vulnerability' && signal.cve).map((signal) => signal.cve));
    assert(uniqueCves.size < data.signals.filter((signal) => signal.kind === 'vulnerability').length, 'Fixture is not demonstrating repeated package/manifest evidence');
    checks.push('Bundled scope and full evidence manifest remain visible in incident response');

    await page.locator('.main-navigation').getByRole('button', { name: /^Web Watch/ }).click();
    const monitor = page.getByTestId('hosted-monitor');
    await monitor.waitFor();
    assert((await monitor.innerText()).includes(data.monitor.id), 'The real hosted monitor ID is missing');
    if (data.monitor.last_run?.status === 'completed') await monitor.getByText('Completed remotely', { exact: true }).waitFor();
    else assert(!(await monitor.innerText()).includes('Completed remotely'), 'An unfinished monitor is presented as completed');
    await monitor.getByText('Webhook ingestion is not implemented.', { exact: false }).waitFor();
    const budget = await page.locator('.context-budget').innerText();
    assert(budget.includes(`${usage.monitor_spent_and_reserved} monitor spent/reserved`), 'Monitor commitments are absent from the budget');
    await page.screenshot({ path: path.join(OUT, 'hosted-monitor.png'), fullPage: true });
    const creditMatch = budget.match(/(\d+) \/ (\d+) credits\s+(\d+) scrape\/search spent · (\d+) monitor spent\/reserved(?: · (\d+) in flight)? · (\d+) available/);
    assert(creditMatch, `Credit totals are incomplete: ${budget}`);
    const [totalCredits, limitValue, ordinaryCredits, monitorCredits, , availableCredits] = creditMatch.slice(1).map(Number);
    const inFlight = Number(creditMatch[5] || 0);
    assert(limitValue === usage.daily_credit_limit, 'The configured credit ceiling is not displayed');
    assert(totalCredits === ordinaryCredits + monitorCredits + inFlight, 'Committed credits do not match their components');
    assert(availableCredits === Math.max(0, limitValue - totalCredits), 'Available credit arithmetic is incorrect');
    assert(budget.includes('additional ordinary requests and new schedules are blocked') === (totalCredits > limitValue), 'The overcommitment warning does not match the configured budget');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.context-budget').scrollIntoViewIfNeeded();
    const budgetMobile = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert(budgetMobile.scrollWidth <= budgetMobile.width + 1, `Mobile budget/monitor overflow: ${JSON.stringify(budgetMobile)}`);
    await page.screenshot({ path: path.join(OUT, 'hosted-monitor-mobile.png'), fullPage: true });
    checks.push('Hosted schedule/run evidence, credit commitments and honest webhook limitation');

    report = {
      ok: !errors.length && !mutations.length,
      target: BASE,
      repository: data.workspace.repository,
      commit: data.workspace.commit_sha,
      coverage: {
        repository_files: coverage.repository_files,
        files_read: coverage.files_read,
        bytes_read: coverage.bytes_read,
        manifests: `${coverage.manifest_files_read}/${coverage.manifest_candidates}`,
        manifest_parse_errors: parseErrors.length,
        source_complete: coverage.source_complete,
        archive_downloaded: coverage.archive_downloaded,
      },
      osv: { eligible: osv.packages_eligible, checked: osv.packages_checked, pending: osv.packages_pending, details_pending: osv.advisory_details_pending },
      findings: data.signals.filter((signal) => signal.kind === 'vulnerability').length,
      unique_cves: uniqueCves.size,
      monitor: { id: data.monitor.id, mode: data.monitor.mode, last_run: data.monitor.last_run },
      budget: usage,
      checks,
      errors,
      browser_mutations: mutations,
    };
    fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  } catch (error) {
    errors.push(`assertion: ${error.message}`);
    await page.screenshot({ path: path.join(OUT, 'failure.png'), fullPage: true }).catch(() => {});
    const navigation = await page.locator('.main-navigation').evaluate((element) => ({ display: getComputedStyle(element).display, visibility: getComputedStyle(element).visibility, buttons: [...element.querySelectorAll('button')].map((button) => ({ text: button.innerText, label: button.getAttribute('aria-label'), visible: !!(button.offsetWidth || button.offsetHeight) })) })).catch((error) => ({ error: error.message }));
    fs.writeFileSync(path.join(OUT, 'failure.json'), JSON.stringify({ error: error.message, url: page.url(), navigation, viewport: page.viewportSize() }, null, 2));
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ...report, ok: !errors.length && !mutations.length, checks, errors, browser_mutations: mutations, artifacts: OUT }, null, 2));
  if (errors.length || mutations.length) process.exitCode = 1;
})();
