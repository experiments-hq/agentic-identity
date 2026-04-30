"""Landing page HTML for ACP Cloud."""

LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACP Cloud — Agent Control Plane</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
               background: #0a0a0f; color: #e0e0e0; min-height: 100vh; }
        .container { max-width: 720px; margin: 0 auto; padding: 80px 24px; }
        h1 { font-size: 2.5rem; font-weight: 700; margin-bottom: 12px; color: #fff; }
        .subtitle { font-size: 1.15rem; color: #888; margin-bottom: 48px; line-height: 1.5; }
        h2 { font-size: 1.3rem; color: #fff; margin-bottom: 16px; }
        .features { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 48px; }
        .feature { background: #14141f; border: 1px solid #222; border-radius: 8px; padding: 16px; }
        .feature strong { color: #7c8aff; }
        pre { background: #14141f; border: 1px solid #222; border-radius: 8px; padding: 20px;
              overflow-x: auto; font-size: 0.85rem; line-height: 1.6; color: #c8d0ff; }
        .code-comment { color: #555; }
        a { color: #7c8aff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .links { margin-top: 32px; display: flex; gap: 24px; flex-wrap: wrap; }
        .links a { background: #14141f; border: 1px solid #222; border-radius: 6px;
                   padding: 10px 18px; font-size: 0.9rem; }
        .links a:hover { border-color: #7c8aff; text-decoration: none; }
        @media (max-width: 600px) { .features { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>Agent Control Plane</h1>
        <p class="subtitle">
            Identity, governance, and observability for AI agents.<br>
            Sign up to get an isolated control plane in 30 seconds.
        </p>
        <div class="features">
            <div class="feature"><strong>Identity</strong><br>Agent JWTs + JWKS offline verification</div>
            <div class="feature"><strong>Policy</strong><br>Declarative YAML guardrails</div>
            <div class="feature"><strong>Approvals</strong><br>Human-in-the-loop gates</div>
            <div class="feature"><strong>Observability</strong><br>Full trace + span telemetry</div>
            <div class="feature"><strong>Budget</strong><br>Token &amp; cost controls</div>
            <div class="feature"><strong>Audit</strong><br>Hash-chained compliance log</div>
        </div>
        <h2>Get Started</h2>
<pre><span class="code-comment"># 1. Sign up (creates your isolated org)</span>
curl -X POST {BASE_URL}/api/cloud/signup \\
  -H "Content-Type: application/json" \\
  -d '{{"org_name": "My Company", "email": "you@example.com"}}'

<span class="code-comment"># Returns: org_id, admin_token, issuer_url, jwks_url, ...</span>

<span class="code-comment"># 2. Register an agent</span>
curl -X POST {BASE_URL}/api/agents/register \\
  -H "x-acp-admin-token: YOUR_ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"org_id": "YOUR_ORG_ID", "team_id": "team-1",
       "display_name": "My Agent", "framework": "langgraph",
       "environment": "production"}}'

<span class="code-comment"># Returns: agent JWT token for offline verification</span>

<span class="code-comment"># 3. Open the console</span>
<span class="code-comment"># {BASE_URL}/console/</span>
<span class="code-comment"># Log in with your admin_token</span></pre>
        <div class="links">
            <a href="/docs">API Docs</a>
            <a href="/console/">Console</a>
            <a href="/.well-known/agent-issuer">Issuer Metadata</a>
            <a href="https://github.com/experiments-hq/agentic-identity">GitHub</a>
        </div>
    </div>
</body>
</html>
"""
