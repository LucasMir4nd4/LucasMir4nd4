"""Gera os cards SVG do perfil (projetos, estatísticas e linguagens) direto da API do GitHub.

Roda no GitHub Actions; os SVGs vão para o branch `output` e são servidos pelo raw.githubusercontent.com,
sem depender de serviços externos que caem ou ficam bloqueados por limite de uso.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "LucasMir4nd4")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"

# Projetos em destaque: nome do repositório -> descrição exibida no card
PINS = {
    "mini-bank-api": "API REST de banco digital com Spring Boot, Spring Security, JPA, PostgreSQL e Flyway.",
    "SnakeGameSpringBoot": "Jogo da cobrinha com back-end em Spring Boot e CRUD de jogadores e pontuações (SQLite).",
    "desafios-java": "Desafios técnicos resolvidos em Java 21, cada um como módulo Maven com testes em JUnit 5.",
    "MailPy": "Aplicação web em Python/Flask que automatiza e-mails de liberação técnica pelo Outlook.",
    "promo-bot-admin": "Painel administrativo em Angular para um bot de ofertas desenvolvido em Spring Boot.",
    "halo-helper": "Extensão para o Google Chrome que agiliza o atendimento de chamados no HaloITSM.",
}

BG, BORDER, TITLE, TEXT, MUTED, ACCENT = "#0d1117", "#30363d", "#58a6ff", "#c9d1d9", "#8b949e", "#a371f7"
FONT = "font-family:'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif"


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"Erro na API do GitHub: {payload['errors']}")
    return payload["data"]


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name description stargazerCount forkCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
      }
    }
  }
}
"""


def wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width and line:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines[:2]


def frame(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{BORDER}"/>'
        f'<g style="{FONT}">{body}</g></svg>'
    )


def pin_card(repo, desc):
    lines = wrap(desc, 58)
    body = (
        f'<path transform="translate(22,22)" fill="{MUTED}" d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/>'
        f'<text x="46" y="35" fill="{TITLE}" font-size="16" font-weight="600">{escape(repo["name"])}</text>'
    )
    for i, line in enumerate(lines):
        body += f'<text x="22" y="{64 + i * 19}" fill="{TEXT}" font-size="13">{escape(line)}</text>'
    lang = repo.get("primaryLanguage") or {}
    x = 22
    if lang:
        body += f'<circle cx="{x + 6}" cy="117" r="6" fill="{lang.get("color") or MUTED}"/>'
        body += f'<text x="{x + 18}" y="121.5" fill="{MUTED}" font-size="12.5">{escape(lang["name"])}</text>'
        x += 30 + len(lang["name"]) * 7.5
    if repo["stargazerCount"]:
        body += f'<text x="{x}" y="121.5" fill="{MUTED}" font-size="12.5">★ {repo["stargazerCount"]}</text>'
    return frame(420, 140, body)


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    i = len(counts) - 1
    if counts and counts[i] == 0:  # o dia de hoje ainda pode não ter contribuição
        i -= 1
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return current, longest


def stats_card(data):
    cc = data["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    current, longest = streaks(days)
    rows = [
        ("Contribuições no último ano", cc["contributionCalendar"]["totalContributions"]),
        ("Commits no último ano", cc["totalCommitContributions"]),
        ("Repositórios públicos", data["repositories"]["totalCount"]),
        ("Sequência atual (dias)", current),
        ("Maior sequência (dias)", longest),
    ]
    body = f'<text x="25" y="38" fill="{TITLE}" font-size="18" font-weight="600">Estatísticas no GitHub</text>'
    for i, (label, value) in enumerate(rows):
        y = 75 + i * 26
        body += f'<circle cx="31" cy="{y - 5}" r="4" fill="{ACCENT}"/>'
        body += f'<text x="45" y="{y}" fill="{TEXT}" font-size="14">{label}:</text>'
        body += f'<text x="330" y="{y}" fill="{TEXT}" font-size="14" font-weight="700" text-anchor="end">{value}</text>'
    return frame(360, 200, body)


def langs_card(data):
    totals = {}
    for repo in data["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            prev = totals.get(name, (0, edge["node"]["color"]))
            totals[name] = (prev[0] + edge["size"], edge["node"]["color"] or MUTED)
    top = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)[:8]
    total = sum(v[0] for _, v in top) or 1
    body = f'<text x="25" y="38" fill="{TITLE}" font-size="18" font-weight="600">Linguagens mais usadas</text>'
    body += '<clipPath id="bar"><rect x="25" y="55" width="310" height="9" rx="4.5"/></clipPath><g clip-path="url(#bar)">'
    x = 25.0
    for _, (size, color) in top:
        w = 310 * size / total
        body += f'<rect x="{x:.2f}" y="55" width="{w + 0.5:.2f}" height="9" fill="{color}"/>'
        x += w
    body += "</g>"
    for i, (name, (size, color)) in enumerate(top):
        cx = 25 + (i % 2) * 160
        cy = 92 + (i // 2) * 26
        body += f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>'
        body += f'<text x="{cx + 16}" y="{cy}" fill="{TEXT}" font-size="13">{escape(name)} <tspan fill="{MUTED}">{size / total * 100:.1f}%</tspan></text>'
    return frame(360, 200, body)


def main():
    data = gql(QUERY, {"login": USER})["user"]
    repos = {r["name"]: r for r in data["repositories"]["nodes"]}
    os.makedirs(OUT, exist_ok=True)
    for name, desc in PINS.items():
        repo = repos.get(name)
        if not repo:
            print(f"Aviso: repositório público '{name}' não encontrado, card ignorado")
            continue
        with open(f"{OUT}/pin-{name}.svg", "w", encoding="utf-8") as f:
            f.write(pin_card(repo, desc))
    with open(f"{OUT}/stats.svg", "w", encoding="utf-8") as f:
        f.write(stats_card(data))
    with open(f"{OUT}/langs.svg", "w", encoding="utf-8") as f:
        f.write(langs_card(data))
    print("Cards gerados em", OUT)


if __name__ == "__main__":
    main()
