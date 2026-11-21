// Fake generation platform: queued -> in_progress -> completed. Prompts with
// "close-up" fail as nsfw, to exercise refunds.
const http = require('http');
const jobs = new Map(); let n = 0;
http.createServer((req, res) => {
  let body = ''; req.on('data', c => body += c); req.on('end', () => {
    res.setHeader('content-type', 'application/json');
    const m = req.url.match(/^\/requests\/([^/]+)\/status/);
    if (req.method === 'GET' && m) {
      const job = jobs.get(m[1]); if (!job) { res.statusCode = 404; return res.end('{"detail":"nope"}'); }
      job.polls++;
      if (job.polls < 2) return res.end(JSON.stringify({ request_id: m[1], status: 'in_progress' }));
      if (job.fail) return res.end(JSON.stringify({ request_id: m[1], status: 'nsfw' }));
      return res.end(JSON.stringify(job.video
        ? { request_id: m[1], status: 'completed', video: { url: `https://example.com/${m[1]}.mp4` } }
        : { request_id: m[1], status: 'completed', images: [{ url: `https://example.com/${m[1]}.png` }] }));
    }
    const input = JSON.parse(body || '{}'); const id = 'req' + (++n);
    jobs.set(id, { polls: 0, video: req.url.includes('video'), fail: (input.prompt || '').includes('close-up') });
    console.log('submit', req.url, id, input.image_urls || input.image_url);
    res.end(JSON.stringify({ request_id: id, status: 'queued' }));
  });
}).listen(3200, () => console.log('mock on 3200'));
