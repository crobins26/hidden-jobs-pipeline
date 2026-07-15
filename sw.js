const CACHE="career-center-v8";
const ASSETS=["./","index.html","styles.css?v=8.0","app.js?v=8.0","manifest.json","icons/icon.svg"];

self.addEventListener("install",event=>{
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));
});

self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);

  if(url.pathname.endsWith("/data/jobs.json")){
    event.respondWith(
      fetch(event.request,{cache:"no-store"})
        .then(response=>response)
        .catch(()=>caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response=>{
        const clone=response.clone();
        caches.open(CACHE).then(cache=>cache.put(event.request,clone));
        return response;
      })
      .catch(()=>caches.match(event.request))
  );
});
