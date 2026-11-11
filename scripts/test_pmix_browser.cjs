/* Real local endpoint E2E. No mocked extraction, quotes, supplier or payment calls. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {spawn}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..');
const out=path.resolve(process.env.LEGION_CAD_EVIDENCE||path.join(root,'cad_evidence'));
fs.mkdirSync(out,{recursive:true});
const fixture=path.join(process.env.LEGION_CAD_EXPERIMENT||path.join(root,'external/cad-experiment'),'tools/pmix-0.16.1/tests/fixtures/synthetic/assembly_properties.stp');
const logfile=fs.openSync(path.join(out,'browser-server.log'),'w');
const port=Number(process.env.LEGION_CAD_TEST_PORT||18896);
const server=spawn(process.env.PYTHON||'python3',['-B','-m','deal_rescue.server','--evidence','demo_evidence','--port',String(port)],{cwd:root,env:process.env,windowsHide:true,stdio:['ignore',logfile,logfile]});
const base=`http://127.0.0.1:${port}`;
(async()=>{
 let browser;const results=[];
 try{
   const ready=()=>new Promise(resolve=>{const req=require('http').get(base,r=>{r.resume();resolve(r.statusCode===200)});req.on('error',()=>resolve(false));req.setTimeout(1000,()=>{req.destroy();resolve(false)})});
   let started=false;for(let i=0;i<50;i++){if(await ready()){started=true;break}await new Promise(r=>setTimeout(r,100));}
   assert(started,'test server must start');
   browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
   for(const width of [1440,390]){
     const page=await browser.newPage({viewport:{width,height:950}});const calls=[];const errors=[];
     page.on('pageerror',e=>errors.push(String(e)));
     page.on('request',r=>{if(r.method()==='POST')calls.push(new URL(r.url()).pathname)});
     try{
       await page.goto(base);await page.locator('#legion-start-drawing').click();
       await page.screenshot({path:path.join(out,`drawing-${width}.png`)});
       await page.locator('#df-file').setInputFiles(fixture);
       await page.locator('#df-form button[type=submit]').click();
       await page.waitForSelector('[data-screen="PARTS"]',{timeout:60000});
       await page.screenshot({path:path.join(out,`parts-${width}.png`)});
       assert.deepEqual(calls,['/api/industrial/engineering-extract']);
       assert(await page.locator('#df-source').isDisabled());
       assert.equal(await page.locator('.df-select').count(),2,'real pmix must extract both components');
       assert((await page.locator('#df-result').innerText()).includes('SYN-STEEL-4'));
       assert((await page.locator('#df-result').innerText()).includes('SYN-ALLOY-17'));
       await page.locator('.df-select').first().check();assert(await page.locator('#df-source').isDisabled());
       await page.locator('#df-parts-consent').check();assert(await page.locator('#df-source').isEnabled());
       // No sourcing until explicit confirmation. Continue is still read-only.
       await page.locator('#df-source').click();await page.waitForSelector('[data-screen="REVIEW"]',{timeout:60000});
       await page.locator('#df-payment-review').click();
       assert((await page.locator('#df-confirm-result').innerText()).includes('No payment'));
       assert(calls.every(p=>['/api/industrial/intake','/api/industrial/engineering-extract'].includes(p)));
       assert.equal(errors.length,0);
       results.push({width,status:'PASS',post_requests:calls,errors});
     }catch(e){results.push({width,status:'FAIL',error:String(e),post_requests:calls,errors});}
     finally{await page.close();}
   }
 }catch(e){results.push({status:'FAIL',error:String(e)});}
 finally{if(browser)await browser.close();server.kill();fs.closeSync(logfile);fs.writeFileSync(path.join(out,'BROWSER_RESULTS.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results,null,2));if(results.length!==2||results.some(r=>r.status!=='PASS'))process.exitCode=1;
})();
