/* Offline browser regression. Render /portal with the app and set NARJIS_PORTAL_HTML. */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const root = process.cwd();
const html = fs.readFileSync(process.env.NARJIS_PORTAL_HTML, 'utf8');
const packages = { packages: [
  {key:'bidaya',name:'البداية',name_en:'Bidaya',price:'790',setup_fee:0,icon:'fas fa-star',tagline:'',tagline_en:'',features:[],features_en:[],coming:[],coming_en:[]},
  {key:'numuw',name:'النمو',name_en:'Growth',price:'1490',setup_fee:99000,icon:'fas fa-star',tagline:'',tagline_en:'',features:[],features_en:[],coming:[],coming_en:[]},
  {key:'sharikat',name:'الشركات',name_en:'Business',price:'2990',setup_fee:199000,icon:'fas fa-star',tagline:'',tagline_en:'',features:[],features_en:[],coming:[],coming_en:[]}
], enterprise:null, addon:{price:'149'}, usage_addons:{} };
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || '/usr/local/bin/chromium', args:['--no-sandbox']});
  let checks = 0;
  try {
    for (const width of [320, 390, 1280]) {
      const page = await browser.newPage({viewport:{width,height:844}});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.route('**/*', route => {
        const u = new URL(route.request().url());
        if (u.origin !== 'http://narjis.test') return route.abort();
        if (u.pathname === '/portal') return route.fulfill({status:200, contentType:'text/html', body:html});
        if (u.pathname === '/api/portal/packages') return route.fulfill({json:packages});
        if (u.pathname === '/api/promo') return route.fulfill({json:{promo:{active:false}}});
        if (u.pathname === '/api/payments/capabilities') return route.fulfill({json:{}});
        if (u.pathname.startsWith('/static/css/')) {
          const file = path.join(root,'src/web',u.pathname);
          if (fs.existsSync(file)) return route.fulfill({status:200,contentType:'text/css',body:fs.readFileSync(file,'utf8')});
        }
        return route.abort();
      });
      await page.goto('http://narjis.test/portal?billing=annual');
      const first=page.locator('.pkg[data-pkg="bidaya"]');
      const second=page.locator('.pkg[data-pkg="numuw"]');
      await first.waitFor();
      assert.equal(await first.getAttribute('role'),'button');
      assert.equal(await first.getAttribute('tabindex'),'0');
      assert.equal(await first.getAttribute('aria-pressed'),'false');
      await first.focus(); await page.keyboard.press('Enter');
      assert.equal(await first.getAttribute('aria-pressed'),'true');
      assert.match(await page.locator('#pkgSummary').innerText(), /فوترة سنوية/);
      await second.focus(); await page.keyboard.press('Space');
      assert.equal(await first.getAttribute('aria-pressed'),'false');
      assert.equal(await second.getAttribute('aria-pressed'),'true');
      assert.match(await page.locator('#pkgSummary').innerText(), /النمو/);
      assert.equal(await page.locator('#regForm').isVisible(),true);
      assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),true,'horizontal overflow at '+width);
      await page.locator('#subscribeBtn').evaluate(el=>el.click());
      await page.waitForFunction(() => document.querySelector('#coSummary').textContent.includes('سنة'));
      assert.match(await page.locator('#coSummary').innerText(), /ثم.*سنة/);
      assert.deepEqual(errors,[]);
      checks += 1;
      await page.close();
    }
    console.log(`PASS: ${checks} viewport scenarios (320, 390, 1280): keyboard Enter/Space, ARIA, annual selection, annual renewal, RTL and overflow; network mocked.`);
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1)});
