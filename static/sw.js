/* ===================================================================
   SERVICE WORKER - CENTRAL DE CHAMADOS BRASFORT (PWA)
   =================================================================== */

const CACHE_VERSION = 'central-chamados-v1.0.0';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `dynamic-${CACHE_VERSION}`;

// Recursos essenciais para funcionamento do shell e modo offline
const PRECACHE_ASSETS = [
    '/offline',
    '/static/css/global.css',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/favicon-32x32.png',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
];

// Instalação do Service Worker: pré-armazena os arquivos do shell
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[PWA SW] Pre-caching recursos estáticos e página offline...');
                return cache.addAll(PRECACHE_ASSETS);
            })
            .then(() => self.skipWaiting())
            .catch((err) => {
                console.warn('[PWA SW] Falha no pre-cache de alguns recursos:', err);
                return self.skipWaiting();
            })
    );
});

// Ativação do Service Worker: remove caches legados
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== STATIC_CACHE && name !== DYNAMIC_CACHE)
                        .map((name) => {
                            console.log('[PWA SW] Removendo cache legado:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => self.clients.claim())
    );
});

// Interceptação de requisições de rede
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // 1. Ignora métodos não-GET (POST, PUT, DELETE, etc. devem ir direto ao servidor Flask)
    if (request.method !== 'GET') {
        return;
    }

    // 2. Ignora esquemas especiais (chrome-extension, etc.)
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // 3. ESTRATÉGIA PARA NAVEGAÇÃO / PÁGINAS HTML: Network First com fallback para Cache e Offline
    const isNavigation = request.mode === 'navigate' || 
                         (request.headers.get('accept') && request.headers.get('accept').includes('text/html'));

    if (isNavigation) {
        event.respondWith(
            fetch(request)
                .then((networkResponse) => {
                    // Se a resposta for válida, armazena uma cópia no cache dinâmico
                    if (networkResponse && networkResponse.status === 200) {
                        const responseClone = networkResponse.clone();
                        caches.open(DYNAMIC_CACHE).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return networkResponse;
                })
                .catch(async () => {
                    console.log('[PWA SW] Rede indisponível para navegação. Tentando cache...');
                    
                    // Tenta encontrar a página solicitada no cache
                    const cachedResponse = await caches.match(request);
                    if (cachedResponse) {
                        return cachedResponse;
                    }

                    // Se não estiver no cache, retorna a página offline pré-armazenada
                    const offlinePage = await caches.match('/offline');
                    if (offlinePage) {
                        return offlinePage;
                    }

                    // Fallback de emergência caso /offline não esteja em cache
                    return new Response(
                        `<!DOCTYPE html>
                        <html lang="pt-br">
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>Central de Chamados - Offline</title>
                            <style>
                                body { background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
                                .card { background: #1e293b; padding: 32px; border-radius: 12px; border: 1px solid #334155; max-width: 450px; }
                                h1 { font-size: 20px; margin-bottom: 12px; }
                                p { color: #94a3b8; font-size: 14px; line-height: 1.5; }
                                button { background: #2563eb; color: #fff; border: 0; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 15px; }
                            </style>
                        </head>
                        <body>
                            <div class="card">
                                <h1>Sem Conexão com o Servidor</h1>
                                <p>Não foi possível conectar ao servidor da Central de Chamados. Verifique se o servidor está ativo (flask run) ou se sua rede está conectada.</p>
                                <button onclick="window.location.reload()">Tentar Reconectar</button>
                            </div>
                        </body>
                        </html>`,
                        {
                            headers: { 'Content-Type': 'text/html; charset=utf-8' }
                        }
                    );
                })
        );
        return;
    }

    // 4. ESTRATÉGIA PARA ARQUIVOS ESTÁTICOS (CSS, JS, IMAGENS, FONTES): Cache First / Stale-While-Revalidate
    const isStaticAsset = url.pathname.startsWith('/static/') ||
                          url.hostname.includes('cdn.jsdelivr.net') ||
                          request.destination === 'style' ||
                          request.destination === 'script' ||
                          request.destination === 'image' ||
                          request.destination === 'font';

    if (isStaticAsset) {
        event.respondWith(
            caches.match(request).then((cachedResponse) => {
                const fetchPromise = fetch(request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseClone = networkResponse.clone();
                        caches.open(STATIC_CACHE).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return networkResponse;
                }).catch(() => {
                    // Silently ignore network failures for background updates
                });

                // Retorna do cache imediatamente se existir, caso contrário aguarda a rede
                return cachedResponse || fetchPromise;
            })
        );
        return;
    }

    // 5. Demais requisições: fetch padrão
    event.respondWith(fetch(request));
});

// Listener para atualização instantânea enviada pelo cliente
self.addEventListener('message', (event) => {
    if (event.data && event.data.action === 'skipWaiting') {
        self.skipWaiting();
    }
});
