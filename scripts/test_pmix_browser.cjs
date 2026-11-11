/* Real local endpoint E2E. No mocked extraction, quotes, supplier or payment calls. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {createHash}=require('crypto');
const {spawn}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[path.join(__dirname,'pmix-browser')]}));
const root=path.resolve(__dirname,'..');
const out=path.resolve(process.env.LEGION_CAD_EVIDENCE||path.join(root,'cad_evidence'));
fs.mkdirSync(out,{recursive:true});
const fixture=path.join(process.env.LEGION_CAD_EXPERIMENT||path.join(root,'external/cad-experiment'),'tools/pmix-0.16.1/tests/fixtures/synthetic/assembly_properties.stp');
const logfile=fs.openSync(path.join(out,'browser-server.log'),'w');
const port=Number(process.env.LEGION_CAD_TEST_PORT||18896);
const server=process.env.LEGION_CAD_BASE_URL?null:spawn(process.env.PYTHON||'python3',['-B','-m','deal_rescue.server','--evidence','demo_evidence','--port',String(port)],{cwd:root,env:process.env,windowsHide:true,stdio:['ignore',logfile,logfile]});
const base=process.env.LEGION_CAD_BASE_URL||`http://127.0.0.1:${port}`;
(async()=>{
 let browser;const results=[];
 try{
   const ready=()=>new Promise(resolve=>{const req=require('http').get(base,r=>{r.resume();resolve(r.statusCode===200)});req.on('error',()=>resolve(false));req.setTimeout(1000,()=>{req.destroy();resolve(false)})});
   let started=false;for(let i=0;i<50;i++){if(await ready()){started=true;break}await new Promise(r=>setTimeout(r,100));}
   assert(started,'test server must start');
   browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
   for(const width of [1440,390]){
     const page=await browser.newPage({viewport:{width,height:950}});const calls=[];const errors=[];const api=[];
     await page.addInitScript(()=>{
       window.cadScreens=[];
       new MutationObserver(records=>{
         for(const record of records){
           if(record.target.id!=='legion-demand-intake')continue;
           const current=record.target.dataset.screen;
           if(current!==window.cadScreens.at(-1))window.cadScreens.push(current);
         }
       }).observe(document,{subtree:true,attributes:true,attributeFilter:['data-screen']});
     });
     page.on('pageerror',e=>errors.push(String(e)));
     page.on('request',r=>{if(r.method()==='POST')calls.push(new URL(r.url()).pathname)});
     const recordResponse=async promise=>{
       const response=await promise;
       const request=response.request();
       const payload=request.postDataJSON();
       const uploaded=payload.file_b64;
       if(uploaded){
         payload.uploaded_sha256=createHash('sha256').update(Buffer.from(uploaded,'base64')).digest('hex');
         delete payload.file_b64;
       }
       const body=await response.json();
       api.push({method:request.method(),url:response.url(),status:response.status(),request:payload,response:body});
       assert(response.ok());
       assert.equal(new URL(response.url()).origin,new URL(base).origin);
       return body;
     };
     try{
       await page.goto(base);await page.locator('#legion-start-drawing').click();
       await page.screenshot({path:path.join(out,`drawing-${width}.png`)});
       await page.locator('#df-file').setInputFiles(fixture);
       const extractedResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/industrial/engineering-extract');
       await page.locator('#df-form button[type=submit]').click();
       const extraction=await recordResponse(extractedResponse);
       assert.equal(extraction.file_sha256,createHash('sha256').update(fs.readFileSync(fixture)).digest('hex'));
       assert.deepEqual(Object.fromEntries(extraction.bom.map(p=>[p.part_no,p.quantity])),{'SYN-BRACKET':1,'SYN-PIN':2});
       await page.waitForSelector('[data-screen="PARTS"]',{timeout:60000});
       await page.screenshot({path:path.join(out,`parts-${width}.png`)});
       assert.deepEqual(calls,['/api/industrial/engineering-extract']);
       assert(await page.locator('#df-source').isDisabled());
       assert.equal(await page.locator('.df-select').count(),2,'real pmix must extract both components');
       assert((await page.locator('#df-result').innerText()).includes('SYN-STEEL-4'));
       assert((await page.locator('#df-result').innerText()).includes('SYN-ALLOY-17'));
       assert(await page.locator('#legion-demand-intake').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'PARTS must fit the supported viewport');
       assert(await page.locator('#df-form').isHidden());
       await page.locator('.df-select').first().check();assert(await page.locator('#df-source').isDisabled());
       await page.locator('#df-parts-consent').check();assert(await page.locator('#df-source').isEnabled());
       // No sourcing until explicit confirmation. Continue is still read-only.
       const reviewResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/industrial/intake');
       await page.locator('#df-source').click();await page.waitForSelector('[data-screen="REVIEW"]',{timeout:60000});
       const review=await recordResponse(reviewResponse);
       await page.screenshot({path:path.join(out,`review-${width}.png`)});
       assert.equal(review.new_paypal_captures,0);assert.equal(review.supplier_requests_sent,0);
       assert.equal(review.live_execution_gate,'Z');assert.equal(review.engineering_verdict,'Z');
       assert.equal(review.parts_confirmed,true);
       await page.locator('#df-payment-review').click();
       assert((await page.locator('#df-confirm-result').innerText()).includes('PayPal authorization: Z'));
       await page.screenshot({path:path.join(out,`paypal-${width}.png`)});
       const stages=await page.evaluate(()=>window.cadScreens);
       assert.deepEqual(stages,['DRAWING','PARTS','LEGION AT WORK','REVIEW','PAYPAL']);
       assert(calls.every(p=>['/api/industrial/intake','/api/industrial/engineering-extract'].includes(p)));
       assert.equal(errors.length,0);
       results.push({width,status:'PASS',stages,post_requests:calls,errors,parts_confirmed:review.parts_confirmed,
         engineering_verdict:review.engineering_verdict,payment_effects:review.new_paypal_captures,
         supplier_requests_sent:review.supplier_requests_sent,horizontal_overflow:false});
     }catch(e){results.push({width,status:'FAIL',error:String(e),post_requests:calls,errors});}
     finally{fs.writeFileSync(path.join(out,`api-${width}.json`),JSON.stringify(api,null,2));await page.close();}
   }
 }catch(e){results.push({status:'FAIL',error:String(e)});}
 finally{if(browser)await browser.close();if(server)server.kill();fs.closeSync(logfile);fs.writeFileSync(path.join(out,'BROWSER_RESULTS.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results,null,2));if(results.length!==2||results.some(r=>r.status!=='PASS'))process.exitCode=1;
})();
