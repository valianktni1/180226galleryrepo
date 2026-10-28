/* Build first. All requests are intercepted; no real galleries, keys or settings. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../build');
(async()=>{const browser=await chromium.launch({executablePath:process.env.WBM_TEST_CHROME,headless:true,args:['--no-sandbox']});try{
 for(const theme of ['light','dark'])for(const width of [320,390,1280]){
  const page=await browser.newPage({viewport:{width,height:900}});let enabled=false,keySaved=false,writes=[];const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(theme=>{localStorage.setItem('admin_token','isolated-fixture');localStorage.setItem('wbm_admin_theme',theme)},theme);
  await page.route('**/*',async route=>{const req=route.request(),u=new URL(req.url());if(u.pathname.startsWith('/api/')){
   if(req.method()!=='GET')writes.push([req.method(),u.pathname,req.postDataJSON()]);
   if(u.pathname==='/api/admin/booking-connection/key'){keySaved=true;enabled=false;return route.fulfill({json:{key:'wbm_gallery_ISOLATED_FIXTURE_ONLY_NOT_A_REAL_KEY',enabled:false}})}
   if(u.pathname==='/api/admin/booking-connection'&&req.method()==='PUT')enabled=req.postDataJSON().enabled;
   return route.fulfill({json:u.pathname==='/api/admin/booking-connection'?{enabled,key_saved:keySaved}:{unread_count:0,notifications:[]}});
  }
  if(u.hostname!=='gallery-fixture.invalid')return route.abort();
  const file=u.pathname.startsWith('/static/')?path.join(root,u.pathname):path.join(root,'index.html');if(!fs.existsSync(file))return route.abort();
  return route.fulfill({path:file});});
  await page.goto('https://gallery-fixture.invalid/admin/settings');await page.getByRole('button',{name:'Booking connection',exact:true}).click();
  await page.getByRole('button',{name:'Create connection key',exact:true}).waitFor();assert.equal(writes.length,0);
  await page.getByRole('button',{name:'Create connection key',exact:true}).click();await page.locator('#booking-connection-key').waitFor();
  assert((await page.locator('#booking-connection-key').inputValue()).startsWith('wbm_gallery_'));
  assert.equal(writes.length,1);assert.equal(enabled,false);
  await page.getByRole('button',{name:'Enable connection',exact:true}).click();await page.getByRole('button',{name:'Pause connection',exact:true}).waitFor();assert.equal(writes.length,2);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${width}/${theme} overflow`);
  assert.deepEqual(errors,[]);
  if(width===390)await page.screenshot({path:`/tmp/wbm-gallery-connection-${theme}.png`});
  await page.close();
 }
 console.log('PASS production gallery build: mobile/desktop and both themes; key creation and enabling are explicit; no automatic writes.');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
