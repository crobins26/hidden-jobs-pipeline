const CACHE="career-center-v11";
const STATIC_ASSETS=[
  "./",
  "index.html",
  "styles.css?v=11.0",
  "app.js?v=11.0",
  "manifest.json",
  "icons/icon.svg"
];

self.addEventListener("install",event=>{
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(STATIC_ASSETS)));
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

  // Configuration and live job data must never be served from an old cache.
  if(
    url.pathname.endsWith("/supabase-config.js") ||
    url.pathname.endsWith("/data/jobs.json")
  ){
    event.respondWith(
      fetch(event.request,{cache:"no-store"})
        .catch(()=>new Response("",{status:503,statusText:"Network required"}))
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
