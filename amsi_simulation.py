"""
AMSI 传播模拟 Demo (Pygame 版 — 阈值感染 · 透明算法 · 弱关系)
================================================================
三栏布局：网络画布(白底) | 算法审计面板(深色) | 人工节点/文本日志(深色)
自适应窗口大小，浅色主题。

运行：pip install pygame-ce && python amsi_simulation.py
"""

import pygame
import threading
import queue
import json
import random
import math
import time
import urllib.request

# ============================================================
#  自适应窗口尺寸
# ============================================================
def get_win_size():
    """根据屏幕分辨率自适应窗口大小（取 88%）"""
    pygame.init()
    info = pygame.display.Info()
    sw, sh = info.current_w, info.current_h
    pygame.quit()
    w = int(sw * 0.88)
    h = int(sh * 0.88)
    # 限制范围
    w = max(960, min(w, 1920))
    h = max(600, min(h, 1080))
    return w, h

WIN_W, WIN_H = get_win_size()
HEADER_H = max(44, int(WIN_H * 0.058))
STATUS_H = max(30, int(WIN_H * 0.038))
SIDE_RATIO = 0.235  # 侧栏占窗口宽度比例
MID_W = max(280, int(WIN_W * SIDE_RATIO))
RIGHT_W = max(280, int(WIN_W * SIDE_RATIO))

NET_X, NET_Y = 0, HEADER_H
NET_W = WIN_W - MID_W - RIGHT_W
NET_H = WIN_H - HEADER_H - STATUS_H
MID_X = NET_W
MID_Y = HEADER_H
MID_H = WIN_H - HEADER_H - STATUS_H
RIGHT_X = NET_W + MID_W
RIGHT_Y = HEADER_H
RIGHT_H = WIN_H - HEADER_H - STATUS_H

# ============================================================
#  浅色主题配色
# ============================================================
# 画布 & 背景
C_CANVAS  = (248, 250, 252)     # 主画布：极浅灰白
C_BG      = (241, 245, 249)    # 窗口底色
# 深色面板
C_PANEL   = (30, 41, 59)        # 侧栏面板：深石板色
C_PANEL_2 = (38, 50, 70)        # 面板内卡片背景
C_HEADER  = (30, 41, 59)       # 顶栏深色
C_STATUS  = (30, 41, 59)       # 状态栏深色
# 边框
C_BORDER  = (203, 213, 225)    # 浅色区域边框
C_BORDER_D= (51, 65, 85)       # 深色区域边框
# 文字
C_TEXT    = (15, 23, 42)        # 浅底文字：近黑
C_TEXT_D  = (226, 232, 240)    # 深底文字：近白
C_DIM     = (100, 116, 139)    # 浅底次要文字
C_DIM_D   = (148, 163, 184)    # 深底次要文字
C_FAINT   = (148, 163, 184)
C_CONTENT = (51, 65, 85)       # 浅底正文
C_CONTENT_D = (203, 213, 225)  # 深底正文
# 节点状态色
C_IDLE    = (148, 163, 184)
C_ACCUM   = (245, 158, 11)
C_HUMAN   = (147, 51, 234)
C_GREEN   = (5, 150, 105)
C_RED     = (220, 38, 38)
C_BLUE    = (37, 99, 235)
C_EDGE    = (186, 194, 204)    # 弱关系边
C_EDGE_D  = (51, 65, 85)       # 深色区边线

CIRCLES = [
    {'name': '科技圈', 'color': (37, 99, 235),  'cx': 0.20, 'cy': 0.52, 'r': 0.15},
    {'name': '劳工圈', 'color': (5, 150, 105),  'cx': 0.50, 'cy': 0.52, 'r': 0.15},
    {'name': '政策圈', 'color': (217, 119, 6),  'cx': 0.80, 'cy': 0.52, 'r': 0.15},
]

# ============================================================
#  API 配置
# ============================================================
API_KEY  = 'sk-27031cc4659c4f0791f3ff3e4e8f228e'
API_URL  = 'https://api.deepseek.com/chat/completions'
MODEL    = 'deepseek-chat'

DEFAULT_PARAMS = {
    'nodesPerCircle': 6, 'avgTheta': 0.45, 'thetaVar': 0.15,
    'w1': 0.35, 'w2': 0.25, 'wFriend': 0.20, 'wHeat': 0.12, 'wRecency': 0.08,
    'topK': 4, 'maxSteps': 8, 'decay': 0.15,
    'useLLM': True, 'maxCalls': 30,
    'seedText': 'AI 技术正在快速取代传统岗位，2024 年就业市场面临严峻挑战。',
}
EMOTIONS   = ['积极', '中性', '消极']
FORMALITIES = ['正式', '非正式', '网络化']
STANCES     = ['支持', '中立', '质疑']

# 字体缩放比例
FS = max(0.75, min(1.3, WIN_W / 1400.0))


def get_font(size, bold=False):
    sz = max(8, int(size * FS))
    for name in ['Microsoft YaHei', 'SimHei', 'SimSun', 'Noto Sans CJK SC', 'Arial']:
        try:
            f = pygame.font.SysFont(name, sz, bold=bold)
            if f.render('测', True, (0, 0, 0)).get_width() > 0:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, sz)


# ============================================================
#  工具
# ============================================================
def draw_dashed_line(surf, color, p1, p2, width=1, dash=6, gap=4):
    x1, y1 = p1; x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1: return
    ux, uy = dx / dist, dy / dist
    t = 0.0
    while t < dist:
        s = t; e = min(t + dash, dist)
        pygame.draw.line(surf, color,
                         (int(x1 + ux * s), int(y1 + uy * s)),
                         (int(x1 + ux * e), int(y1 + uy * e)), width)
        t += dash + gap

def draw_dashed_circle(surf, color, center, radius, dash=6, gap=6, width=1):
    circumference = 2 * math.pi * radius
    n = max(8, int(circumference / (dash + gap)))
    for i in range(n):
        a1 = (i * (dash + gap)) / circumference * math.tau
        a2 = ((i * (dash + gap) + dash) / circumference) * math.tau
        pygame.draw.line(surf, color,
                         (center[0] + math.cos(a1) * radius, center[1] + math.sin(a1) * radius),
                         (center[0] + math.cos(a2) * radius, center[1] + math.sin(a2) * radius), width)

def draw_arc(surf, color, center, radius, start_angle, end_angle, width=3):
    steps = max(8, int(abs(end_angle - start_angle) * radius / 2))
    pts = [(center[0] + math.cos(start_angle + (end_angle - start_angle) * i / steps) * radius,
            center[1] + math.sin(start_angle + (end_angle - start_angle) * i / steps) * radius)
           for i in range(steps + 1)]
    if len(pts) >= 2:
        pygame.draw.lines(surf, color, False, pts, width)

def wrap_text(text, font, max_w):
    lines, cur = [], ''
    for ch in text:
        if font.size(cur + ch)[0] > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur: lines.append(cur)
    return lines


# ============================================================
#  节点 & 活跃文本
# ============================================================
class Node:
    __slots__ = ('id', 'circle', 'x', 'y', 'state', 'style',
                 'theta', 'stimulus', 'text', 'parent_text_id',
                 'receive_step', 'pulse', 'is_human', 'friends')
    def __init__(self, nid, circle, x, y, is_human=False, params=None):
        self.id = nid; self.circle = circle; self.x = x; self.y = y
        self.state = 'idle'
        self.style = {'emotion': random.choice(EMOTIONS),
                      'formality': random.choice(FORMALITIES),
                      'stance': random.choice(STANCES)}
        p = params or DEFAULT_PARAMS
        self.theta = max(0.1, min(0.95, p['avgTheta'] + (random.random() - 0.5) * 2 * p['thetaVar']))
        self.stimulus = 0.0; self.text = None; self.parent_text_id = None
        self.receive_step = -1; self.pulse = 0.0
        self.is_human = is_human; self.friends = []

class ActiveText:
    __slots__ = ('text', 'style', 'origin_circle', 'origin_node', 'origin_id', 'step', 'heat')
    def __init__(self, text, style, origin_circle, origin_node, origin_id, step, heat):
        self.text = text; self.style = style; self.origin_circle = origin_circle
        self.origin_node = origin_node; self.origin_id = origin_id
        self.step = step; self.heat = heat


# ============================================================
#  模拟引擎
# ============================================================
class Simulation:
    def __init__(self):
        self.nodes = []; self.active_texts = []; self.time_step = 0
        self.running = False; self.waiting_human = False; self.api_calls = 0
        self.params = dict(DEFAULT_PARAMS)
        self.human_node = None; self.pending_human = None
        self.audit_rounds = []; self.log_q = queue.Queue(); self._stop = False

    def build(self):
        self.nodes = []
        n = self.params['nodesPerCircle']
        for c in range(3):
            ci = CIRCLES[c]
            for i in range(n):
                ang = (i / n) * math.tau - math.pi / 2
                jitter = 0.75 + random.random() * 0.4
                self.nodes.append(Node(len(self.nodes), c,
                    ci['cx'] + math.cos(ang) * ci['r'] * jitter,
                    ci['cy'] + math.sin(ang) * ci['r'] * jitter * 1.5, params=self.params))
        hn = Node(len(self.nodes), 0, 0.5, 0.08, is_human=True, params=self.params)
        hn.style = {'emotion': '中性', 'formality': '非正式', 'stance': '中立'}
        self.nodes.append(hn); self.human_node = hn
        for c in range(3):
            grp = [nd for nd in self.nodes if nd.circle == c and not nd.is_human]
            for nd in grp:
                others = [x for x in grp if x.id != nd.id]
                k = 2 + random.randint(0, 1); random.shuffle(others)
                nd.friends = [x.id for x in others[:k]]
        tech = [nd for nd in self.nodes if nd.circle == 0 and not nd.is_human]
        hn.friends = [nd.id for nd in tech[:2]]

    def reset(self):
        self._stop = True; time.sleep(0.05); self._stop = False
        self.build(); self.active_texts = []; self.time_step = 0; self.api_calls = 0
        self.waiting_human = False; self.audit_rounds = []; self.pending_human = None
        self.running = False
        while not self.log_q.empty(): self.log_q.get_nowait()

    def _style_sim(self, a, b):
        s = 0
        if a['emotion'] == b['emotion']: s += 0.4
        if a['formality'] == b['formality']: s += 0.3
        if a['stance'] == b['stance']: s += 0.3
        return s

    def _circle_overlap(self, text_origin, node_circle):
        if text_origin == node_circle: return 1
        d = abs(text_origin - node_circle)
        return 0.35 if d == 1 else 0.15

    def _friend_signal(self, atext, node):
        if not node.friends: return 0
        count = 0
        for fid in node.friends:
            f = self.nodes[fid]
            if f.state == 'infected' and f.text:
                if f.text == atext.text: count += 1
                elif atext.origin_id and f.parent_text_id == atext.origin_id: count += 1
        return count / max(1, len(node.friends))

    def _compute_ralg(self, atext, node):
        p = self.params
        sim = self._style_sim(atext.style, node.style)
        overlap = self._circle_overlap(atext.origin_circle, node.circle)
        fsig = self._friend_signal(atext, node)
        heat = atext.heat
        recency = max(0, 1 - (self.time_step - atext.step) * 0.15)
        contrib = {'sim': p['w1']*sim, 'overlap': p['w2']*overlap,
                   'friend': p['wFriend']*fsig, 'heat': p['wHeat']*heat,
                   'recency': p['wRecency']*recency}
        return {'total': sum(contrib.values()), 'contrib': contrib,
                'raw': {'sim': sim, 'overlap': overlap, 'fsig': fsig, 'heat': heat, 'recency': recency}}

    def _generate(self, src_text, node):
        if not self.params['useLLM'] or self.api_calls >= self.params['maxCalls']:
            return self._template(src_text, node)
        self.api_calls += 1
        desc = f"情感：{node.style['emotion']}；语体：{node.style['formality']}；立场：{node.style['stance']}"
        sys_prompt = (f'你是一个社交媒体用户，文本风格为【{desc}】。'
                       '请将用户提供的文本改写为符合你风格的版本：'
                       '保留核心事实，调整表达方式、情感基调和句式。'
                       '直接输出改写结果，60字以内，不要任何前缀解释。')
        body = json.dumps({'model': MODEL, 'messages': [
            {'role': 'system', 'content': sys_prompt},
            {'role': 'user', 'content': src_text}],
            'temperature': 0.9, 'max_tokens': 150}).encode('utf-8')
        try:
            req = urllib.request.Request(API_URL, data=body,
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return (data['choices'][0]['message']['content'] or '').strip()
        except Exception as e:
            print(f'[LLM] 失败，回退: {e}')
            return self._template(src_text, node)

    def _template(self, text, node):
        prefs = {'积极': ['好消息！', '值得关注，'], '中性': ['', '据报道，'], '消极': ['令人担忧，', '警惕！']}
        sufs = {'支持': '——应积极应对。', '中立': '——值得持续观察。', '质疑': '——但风险是否可控？'}
        return random.choice(prefs[node.style['emotion']]) + text[:40] + sufs[node.style['stance']]

    def run_one_step(self):
        if self.waiting_human: return False
        self.time_step += 1
        decay = self.params['decay']
        for n in self.nodes:
            if n.state != 'infected':
                n.stimulus *= (1 - decay)
                if n.stimulus < 0.01: n.stimulus = 0
        candidates = [n for n in self.nodes if n.state != 'infected']
        if not candidates or not self.active_texts: return False
        scored = []
        for n in candidates:
            best_t, best_calc = None, None
            for t in self.active_texts:
                calc = self._compute_ralg(t, n)
                if best_calc is None or calc['total'] > best_calc['total']:
                    best_t, best_calc = t, calc
            scored.append({'node': n, 'text': best_t, 'calc': best_calc})
        scored.sort(key=lambda x: x['calc']['total'], reverse=True)
        top_k = scored[:self.params['topK']]
        audit = {'step': self.time_step, 'entries': [{
            'node': x['node'], 'text': x['text'], 'calc': x['calc'],
            'projected': x['node'].stimulus + x['calc']['total'], 'theta': x['node'].theta}
            for x in top_k]}
        self.audit_rounds.append(audit)
        self.log_q.put(('audit', audit, None, None))
        for x in top_k:
            origin = x['text'].origin_node
            self.log_q.put(('arrow', origin.id, x['node'].id, CIRCLES[x['node'].circle]['color']))
            x['node'].pulse = 1.0
        time.sleep(0.55)
        for x in top_k:
            if self._stop: return False
            node, calc = x['node'], x['calc']
            if node.is_human:
                node.stimulus += calc['total']
                self.waiting_human = True
                self.pending_human = (x['text'], calc, node)
                self.log_q.put(('human', x['text'], calc, node))
                return True
            node.stimulus += calc['total']
            if node.stimulus >= node.theta:
                new_text = self._generate(x['text'].text, node)
                node.state = 'infected'; node.text = new_text
                node.parent_text_id = x['text'].origin_id
                node.receive_step = self.time_step; node.stimulus = 0
                origin_id = f'n{node.id}_s{self.time_step}'
                self.active_texts.append(ActiveText(new_text, dict(node.style), node.circle, node, origin_id, self.time_step, 0.6))
                for t in self.active_texts: t.heat *= 0.9
                self.log_q.put(('log', node, new_text, False))
                self.log_q.put(('verdict', node.id, 'PASS', calc))
            else:
                node.state = 'accumulating'
                self.log_q.put(('verdict', node.id, 'ACCUM', calc))
        self.log_q.put(('status', None, None, None))
        return True

    def human_decide(self, action, rewritten_text=None):
        if not self.pending_human: return
        atext, calc, node = self.pending_human
        if action == 'ignore':
            node.state = 'accumulating'
            self.log_q.put(('log_human', node, '【忽略推送】', False))
        else:
            text = rewritten_text if rewritten_text else atext.text
            if action == 'rewrite' and rewritten_text is None:
                text = self._generate(atext.text, node)
            node.state = 'infected'; node.text = text
            node.receive_step = self.time_step; node.stimulus = 0
            origin_id = f'human_s{self.time_step}'
            self.active_texts.append(ActiveText(text, dict(node.style), node.circle, node, origin_id, self.time_step, 0.6))
            self.log_q.put(('log_human', node, text, True))
            self.log_q.put(('verdict', node.id, 'PASS', calc))
        self.waiting_human = False; self.pending_human = None
        self.log_q.put(('status', None, None, None))

    def run(self):
        if self.running: return
        self.reset()
        seed = self.nodes[0]
        seed.state = 'infected'; seed.text = self.params['seedText']
        seed.receive_step = 0; seed.pulse = 1.0
        self.active_texts = [ActiveText(self.params['seedText'], dict(seed.style), seed.circle, seed, 'seed', 0, 1.0)]
        self.log_q.put(('log', seed, self.params['seedText'], True))
        self.log_q.put(('status', None, None, None))
        self.running = True
        while self.running and self.time_step < self.params['maxSteps']:
            if self._stop: break
            cont = self.run_one_step()
            if self.waiting_human:
                while self.waiting_human and not self._stop: time.sleep(0.05)
                if self._stop: break
                time.sleep(0.3)
            if not cont: break
            time.sleep(0.4)
        self.running = False
        self.log_q.put(('done', None, None, None))


# ============================================================
#  UI 组件
# ============================================================
class Button:
    def __init__(self, rect, text, cb, color=(37, 99, 235)):
        self.rect = pygame.Rect(rect); self.text = text; self.cb = cb
        self.base = color; self.hover = False; self.disabled = False
    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.hover and not self.disabled and self.cb: self.cb()
    def draw(self, sc, font, dark=True):
        if self.disabled:
            c = (71, 85, 105)
        elif self.hover:
            c = tuple(min(255, v + 25) for v in self.base)
        else:
            c = self.base
        pygame.draw.rect(sc, c, self.rect, border_radius=5)
        tc = (255, 255, 255) if dark else C_TEXT
        ts = font.render(self.text, True, tc)
        sc.blit(ts, ts.get_rect(center=self.rect.center))

class TextInput:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect); self.text = ''; self.active = False; self.cursor_blink = 0
    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.active = self.rect.collidepoint(ev.pos)
        elif ev.type == pygame.KEYDOWN and self.active:
            if ev.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif ev.unicode and ev.unicode.isprintable() and len(self.text) < 120:
                self.text += ev.unicode
    def update(self): self.cursor_blink = (self.cursor_blink + 1) % 60
    def draw(self, sc, font):
        c = (37, 99, 235) if self.active else C_BORDER_D
        pygame.draw.rect(sc, C_PANEL_2, self.rect, border_radius=5)
        pygame.draw.rect(sc, c, self.rect, 1, border_radius=5)
        show = self.text + ('|' if self.active and self.cursor_blink < 30 else '')
        for i, line in enumerate(wrap_text(show, font, self.rect.w - 16)):
            sc.blit(font.render(line, True, C_TEXT_D), (self.rect.x + 8, self.rect.y + 6 + i * 18))


# ============================================================
#  主程序
# ============================================================
def main():
    pygame.init()
    pygame.display.set_caption('文本主体传播模拟 · 阈值感染 · 透明算法')
    sc = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()

    F_TITLE  = get_font(14, bold=True)
    F_SUB    = get_font(11)
    F_BTN    = get_font(12)
    F_BODY   = get_font(12)
    F_SMALL  = get_font(10)
    F_TINY   = get_font(10, bold=True)
    F_NODE   = get_font(10, bold=True)
    F_LEGEND = get_font(11)
    F_MONO   = get_font(10)
    F_AUDIT  = get_font(10)
    F_HEAD   = get_font(11, bold=True)
    F_STATUS = get_font(10)

    sim = Simulation(); sim.build()
    log_entries = []; audit_rounds = []; arrows = []; verdicts = {}

    def start_sim():
        if not sim.running:
            log_entries.clear(); audit_rounds.clear(); arrows.clear(); verdicts.clear()
            threading.Thread(target=sim.run, daemon=True).start()
    def do_reset():
        if not sim.running:
            sim.reset(); log_entries.clear(); audit_rounds.clear(); arrows.clear(); verdicts.clear()
    def toggle_llm():
        sim.params['useLLM'] = not sim.params['useLLM']
        btn_llm.text = f"LLM: {'开' if sim.params['useLLM'] else '关'}"
    def step_sim():
        if sim.running and not sim.waiting_human:
            threading.Thread(target=sim.run_one_step, daemon=True).start()

    btn_y = (HEADER_H - 30) // 2
    btn_start = Button((WIN_W - 350, btn_y, 80, 30), '▶ 开始', start_sim)
    btn_step  = Button((WIN_W - 264, btn_y, 80, 30), '⏭ 单步', step_sim, color=(71, 85, 105))
    btn_reset = Button((WIN_W - 178, btn_y, 70, 30), '重置', do_reset, color=(71, 85, 105))
    btn_llm   = Button((WIN_W - 102, btn_y, 90, 30), 'LLM: 开', toggle_llm, color=(71, 85, 105))
    buttons = [btn_start, btn_step, btn_reset, btn_llm]

    human_buttons = []; human_rewrite_input = None

    def setup_human_ui(text, calc, node):
        nonlocal human_rewrite_input, human_buttons
        rw_y = RIGHT_Y + 280
        human_rewrite_input = TextInput((RIGHT_X + 16, rw_y, RIGHT_W - 32, 70))
        def do_ignore(): sim.human_decide('ignore')
        def do_forward(): sim.human_decide('forward')
        def do_rewrite():
            rw = human_rewrite_input.text.strip() if human_rewrite_input else ''
            sim.human_decide('rewrite', rw if rw else None)
        bx = RIGHT_X + 16; by = RIGHT_Y + 365
        human_buttons = [
            Button((bx, by, 100, 30), '忽略', do_ignore, color=(71, 85, 105)),
            Button((bx + 108, by, 100, 30), '直接转发', do_forward, color=(5, 150, 105)),
            Button((bx + 216, by, 120, 30), '改写转发', do_rewrite, color=(37, 99, 235)),
        ]

    running = True
    while running:
        clock.tick(60)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE: running = False
            for b in buttons: b.handle(ev)
            if sim.waiting_human and human_buttons:
                for b in human_buttons: b.handle(ev)
            if human_rewrite_input: human_rewrite_input.handle(ev)

        btn_start.disabled = sim.running
        btn_step.disabled = not sim.running or sim.waiting_human
        btn_reset.disabled = sim.running
        if sim.running: btn_start.text = '传播中...'
        elif sim.time_step > 0: btn_start.text = '▶ 重新开始'
        else: btn_start.text = '▶ 开始'

        while not sim.log_q.empty():
            try:
                kind, a, b, c = sim.log_q.get_nowait()
                if kind == 'log':
                    node, text, is_seed = a, b, c
                    log_entries.append({'nid': node.id, 'circle': node.circle,
                        'emotion': node.style['emotion'], 'stance': node.style['stance'],
                        'text': text, 'seed': is_seed, 'human': node.is_human})
                elif kind == 'log_human':
                    node, text, is_seed = a, b, c
                    log_entries.append({'nid': node.id, 'circle': node.circle,
                        'emotion': node.style['emotion'], 'stance': node.style['stance'],
                        'text': text, 'seed': is_seed, 'human': True})
                elif kind == 'audit': audit_rounds.append(a)
                elif kind == 'arrow':
                    arrows.append({'from_id': a, 'to_id': b, 't': 0, 'color': c})
                elif kind == 'verdict': verdicts[a] = (b, c)
                elif kind == 'human': setup_human_ui(a, b, c)
            except queue.Empty: break

        for ar in arrows: ar['t'] += 0.045
        arrows = [a for a in arrows if a['t'] < 1.0]
        for n in sim.nodes:
            if n.pulse > 0: n.pulse = max(0, n.pulse - 0.05)

        # ===================== 绘制 =====================
        sc.fill(C_BG)

        # ---- 顶栏（深色）----
        pygame.draw.rect(sc, C_HEADER, (0, 0, WIN_W, HEADER_H))
        ty = (HEADER_H - F_TITLE.get_height()) // 2
        sc.blit(F_TITLE.render('文本主体传播模拟', True, C_TEXT_D), (18, ty))
        sub = F_SUB.render('阈值感染 · 透明算法 · 弱关系嵌入', True, C_DIM_D)
        sc.blit(sub, (18 + F_TITLE.size('文本主体传播模拟')[0] + 8, ty + 3))
        for b in buttons: b.draw(sc, F_BTN)

        # ---- 网络画布（白色）----
        pygame.draw.rect(sc, C_CANVAS, (NET_X, NET_Y, NET_W, NET_H))

        # 圈层背景
        for ci in CIRCLES:
            cx = NET_X + int(ci['cx'] * NET_W)
            cy = NET_Y + int(ci['cy'] * NET_H)
            cr = int(ci['r'] * NET_H)
            s = pygame.Surface((cr*2+4, cr*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*ci['color'], 15), (cr+2, cr+2), cr)
            sc.blit(s, (cx-cr-2, cy-cr-2))
            draw_dashed_circle(sc, (*ci['color'], 60), (cx, cy), cr, 6, 6, 1)
            ns = F_LEGEND.render(ci['name'], True, ci['color'])
            sc.blit(ns, ns.get_rect(center=(cx, cy - cr - 14)))

        # 弱关系边
        for n in sim.nodes:
            for fid in n.friends:
                f = sim.nodes[fid]
                if f.id <= n.id: continue
                draw_dashed_line(sc, C_EDGE,
                    (NET_X + int(n.x * NET_W), NET_Y + int(n.y * NET_H)),
                    (NET_X + int(f.x * NET_W), NET_Y + int(f.y * NET_H)), 1, 2, 3)

        # 算法推送箭头
        for ar in arrows:
            src = sim.nodes[ar['from_id']]; tgt = sim.nodes[ar['to_id']]
            fx = NET_X + int(src.x * NET_W); fy = NET_Y + int(src.y * NET_H)
            tx = NET_X + int(tgt.x * NET_W); ty = NET_Y + int(tgt.y * NET_H)
            t = ar['t']; mx = (fx + tx) / 2; my = min(fy, ty) - 30
            cx = int((1-t)*(1-t)*fx + 2*(1-t)*t*mx + t*t*tx)
            cy = int((1-t)*(1-t)*fy + 2*(1-t)*t*my + t*t*ty)
            if (1-t) * 220 > 0:
                draw_dashed_line(sc, ar['color'], (fx, fy), (cx, cy), 2, 8, 0)

        # 节点
        for n in sim.nodes:
            x = NET_X + int(n.x * NET_W); y = NET_Y + int(n.y * NET_H)
            base_r = 17 if n.is_human else 13
            if n.pulse > 0:
                gr = int(base_r + 13 * n.pulse)
                gs = pygame.Surface((gr*2+4, gr*2+4), pygame.SRCALPHA)
                gc = C_HUMAN if n.is_human else C_ACCUM
                pygame.draw.circle(gs, (*gc, int(90 * n.pulse)), (gr+2, gr+2), gr)
                sc.blit(gs, (x-gr-2, y-gr-2))
            if n.is_human: fc = C_HUMAN
            elif n.state == 'infected': fc = CIRCLES[n.circle]['color']
            elif n.state == 'accumulating': fc = C_ACCUM
            else: fc = C_IDLE
            pygame.draw.circle(sc, fc, (x, y), base_r)
            pygame.draw.circle(sc, (255, 255, 255), (x, y), base_r, 2)
            label = '人' if n.is_human else str(n.id + 1)
            ns = F_NODE.render(label, True, (255, 255, 255))
            sc.blit(ns, ns.get_rect(center=(x, y)))
            if n.state == 'accumulating' and n.stimulus > 0.05:
                ratio = min(1, n.stimulus / n.theta)
                ring_c = C_ACCUM if ratio > 0.7 else C_DIM
                draw_arc(sc, ring_c, (x, y), base_r + 3, -math.pi/2, -math.pi/2 + ratio * math.tau, 3)

        # 图例（浅色面板）
        lg_w, lg_h = 180, 110
        lg_x, lg_y = 12, NET_Y + NET_H - lg_h - 12
        lg = pygame.Surface((lg_w, lg_h), pygame.SRCALPHA)
        lg.fill((255, 255, 255, 230))
        pygame.draw.rect(lg, C_BORDER, (0, 0, lg_w, lg_h), 1, border_radius=7)
        lg.blit(F_LEGEND.render('节点状态', True, C_DIM), (10, 6))
        for i, (c, label) in enumerate([
            (C_IDLE, '未接收'), (C_ACCUM, '累积中'), (C_BLUE, '已转发'), (C_HUMAN, '人工节点')]):
            yy = 24 + i * 18
            pygame.draw.circle(lg, c, (20, yy + 7), 6)
            lg.blit(F_LEGEND.render(label, True, C_CONTENT), (34, yy))
        sc.blit(lg, (lg_x, lg_y))

        # 提示框（浅色）
        hw, hh = 260, 65
        hx, hy = 12, NET_Y + 12
        hs = pygame.Surface((hw, hh), pygame.SRCALPHA)
        hs.fill((255, 255, 255, 230))
        pygame.draw.rect(hs, C_BORDER, (0, 0, hw, hh), 1, border_radius=7)
        hs.blit(F_HEAD.render('传播机制', True, C_TEXT), (10, 6))
        for i, line in enumerate(['算法推送候选文本 → 节点累积刺激值',
                                   '→ 达到阈值 ε_B → 触发改写转发',
                                   '同圈层弱关系作为朋友信号进入评分']):
            hs.blit(F_SMALL.render(line, True, C_DIM), (10, 24 + i * 14))
        sc.blit(hs, (hx, hy))

        # ---- 中栏：算法审计（深色面板）----
        pygame.draw.rect(sc, C_PANEL, (MID_X, MID_Y, MID_W, MID_H))
        pygame.draw.line(sc, C_BORDER_D, (MID_X, MID_Y), (MID_X, MID_Y + MID_H))
        sc.blit(F_HEAD.render('算法审计', True, C_DIM_D), (MID_X + 12, MID_Y + 10))
        pygame.draw.line(sc, C_BORDER_D, (MID_X, MID_Y + 34), (MID_X + MID_W, MID_Y + 34))

        audit_y_cur = MID_Y + 42; max_y = MID_Y + MID_H - 5
        for audit in reversed(audit_rounds[-4:]):
            if audit_y_cur > max_y: break
            box_h = 16
            for e in audit['entries']: box_h += 60
            if audit_y_cur + box_h > max_y: break
            bg = pygame.Surface((MID_W - 24, box_h), pygame.SRCALPHA)
            bg.fill((C_PANEL_2[0], C_PANEL_2[1], C_PANEL_2[2], 255))
            pygame.draw.rect(bg, C_BLUE, (0, 0, 2, box_h))
            bg.blit(F_AUDIT.render(f"▸ 第 {audit['step']} 步 · Top-{len(audit['entries'])} 推送", True, (96, 165, 250)), (8, 6))
            ey = 24
            for e in audit['entries']:
                nd = e['node']; cc = CIRCLES[nd.circle]['color']
                name = '人' if nd.is_human else f'节点 {nd.id+1}'
                bg.blit(F_SMALL.render(name, True, C_TEXT_D), (10, ey))
                tag_s = F_TINY.render(CIRCLES[nd.circle]['name'], True, cc)
                tag_bg = pygame.Surface((tag_s.get_width()+8, tag_s.get_height()+2), pygame.SRCALPHA)
                tag_bg.fill((*cc, 40))
                tag_bg.blit(tag_s, (4, 1))
                bg.blit(tag_bg, (10 + F_SMALL.size(name)[0] + 6, ey))
                for fl in [
                    f"R = {e['calc']['contrib']['sim']:.2f}(内容) + {e['calc']['contrib']['overlap']:.2f}(圈层)",
                    f"  + {e['calc']['contrib']['friend']:.2f}(朋友) + {e['calc']['contrib']['heat']:.2f}(热度)",
                    f"  + {e['calc']['contrib']['recency']:.2f}(时效) = {e['calc']['total']:.3f}"]:
                    bg.blit(F_MONO.render(fl, True, C_DIM_D), (14, ey + 14)); ey += 13
                if nd.id in verdicts:
                    v, _ = verdicts[nd.id]
                    if v == 'PASS':
                        bg.blit(F_SMALL.render(f"✅ 达到阈值，触发转发 · 阈值 {e['theta']:.2f}", True, C_GREEN), (10, ey))
                    else:
                        bg.blit(F_SMALL.render(f"⏳ 未达阈值，累积中 · {nd.stimulus:.2f}/{e['theta']:.2f}", True, C_ACCUM), (10, ey))
                else:
                    bg.blit(F_SMALL.render(f"刺激: {nd.stimulus:.2f}+{e['calc']['total']:.2f}={e['projected']:.2f}/{e['theta']:.2f}", True, C_DIM_D), (10, ey))
                ey += 16
                bar_w = MID_W - 50; ratio = min(1, e['projected'] / e['theta'])
                pygame.draw.rect(bg, (51, 65, 85), (10, ey, bar_w, 3), border_radius=2)
                pygame.draw.rect(bg, C_BLUE, (10, ey, int(bar_w * ratio), 3), border_radius=2)
                ey += 8
            sc.blit(bg, (MID_X + 10, audit_y_cur))
            audit_y_cur += box_h + 8

        if not audit_rounds:
            empty = F_SMALL.render('点击「开始」后', True, C_DIM_D)
            sc.blit(empty, empty.get_rect(center=(MID_X + MID_W//2, MID_Y + MID_H//2 - 10)))
            empty2 = F_SMALL.render('此处实时展示算法推送计算过程', True, C_DIM_D)
            sc.blit(empty2, empty2.get_rect(center=(MID_X + MID_W//2, MID_Y + MID_H//2 + 8)))

        # ---- 右栏（深色面板）----
        pygame.draw.rect(sc, C_PANEL, (RIGHT_X, RIGHT_Y, RIGHT_W, RIGHT_H))
        pygame.draw.line(sc, C_BORDER_D, (RIGHT_X, RIGHT_Y), (RIGHT_X, RIGHT_Y + RIGHT_H))

        if sim.waiting_human and sim.pending_human:
            atext, calc, node = sim.pending_human
            sc.blit(F_HEAD.render('人工节点 · 算法推送到达', True, C_HUMAN), (RIGHT_X + 12, RIGHT_Y + 10))
            pygame.draw.line(sc, C_BORDER_D, (RIGHT_X, RIGHT_Y + 34), (RIGHT_X + RIGHT_W, RIGHT_Y + 34))
            info_y = RIGHT_Y + 42
            for i, line in enumerate([
                f"来源圈层：{CIRCLES[atext.origin_circle]['name']}",
                f"R_alg = {calc['total']:.3f}",
                f"累积刺激：{node.stimulus:.2f} / 阈值 {node.theta:.2f}",
                f"内容{calc['contrib']['sim']:.2f} 圈层{calc['contrib']['overlap']:.2f}",
                f"朋友{calc['contrib']['friend']:.2f} 热度{calc['contrib']['heat']:.2f}"]):
                sc.blit(F_MONO.render(line, True, C_DIM_D), (RIGHT_X + 14, info_y + i * 16))
            text_y = info_y + 90
            sc.blit(F_SMALL.render('推送内容：', True, C_DIM_D), (RIGHT_X + 14, text_y))
            for i, line in enumerate(wrap_text(atext.text, F_BODY, RIGHT_W - 28)):
                sc.blit(F_BODY.render(line, True, C_TEXT_D), (RIGHT_X + 14, text_y + 18 + i * 18))
            rw_y = text_y + 80
            sc.blit(F_SMALL.render('改写转发（可编辑）：', True, C_DIM_D), (RIGHT_X + 14, rw_y))
            if human_rewrite_input:
                human_rewrite_input.update(); human_rewrite_input.draw(sc, F_BODY)
            for b in human_buttons: b.draw(sc, F_BTN)
        else:
            sc.blit(F_HEAD.render('文本日志', True, C_DIM_D), (RIGHT_X + 12, RIGHT_Y + 10))
            pygame.draw.line(sc, C_BORDER_D, (RIGHT_X, RIGHT_Y + 34), (RIGHT_X + RIGHT_W, RIGHT_Y + 34))
            log_y = RIGHT_Y + 42; log_bot = RIGHT_Y + RIGHT_H - 5
            card_w = RIGHT_W - 24; y_cur = log_bot
            for entry in reversed(log_entries):
                cc = C_HUMAN if entry['human'] else CIRCLES[entry['circle']]['color']
                meta = (f"{'人' if entry['human'] else '节点'+str(entry['nid']+1)}  "
                        f"{CIRCLES[entry['circle']]['name']}  {entry['emotion']}/{entry['stance']}")
                meta_s = F_SMALL.render(meta, True, C_DIM_D)
                lines = wrap_text(entry['text'], F_BODY, card_w - 20)
                card_h = 6 + 14 + len(lines) * 18 + 6
                y_cur -= card_h + 6
                if y_cur < log_y: break
                cs = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                cs.fill((C_PANEL_2[0], C_PANEL_2[1], C_PANEL_2[2], 255))
                pygame.draw.rect(cs, cc, (0, 0, 3, card_h))
                cs.blit(meta_s, (8, 4))
                if entry['seed']:
                    st = F_TINY.render('种子', True, (120, 53, 15))
                    sb = pygame.Surface((st.get_width()+8, st.get_height()+2), pygame.SRCALPHA)
                    sb.fill((251, 191, 36)); sb.blit(st, (4, 1))
                    cs.blit(sb, (8 + meta_s.get_width() + 6, 4))
                for i, line in enumerate(lines):
                    cs.blit(F_BODY.render(line, True, C_CONTENT_D), (8, 18 + i * 18))
                sc.blit(cs, (RIGHT_X + 10, y_cur))
            if not log_entries:
                empty = F_SMALL.render('尚无记录', True, C_DIM_D)
                sc.blit(empty, empty.get_rect(center=(RIGHT_X + RIGHT_W//2, RIGHT_Y + RIGHT_H//2)))

        # ---- 状态栏（深色）----
        sb_y = WIN_H - STATUS_H
        pygame.draw.rect(sc, C_STATUS, (0, sb_y, WIN_W, STATUS_H))
        infected = sum(1 for n in sim.nodes if n.state == 'infected')
        sy = sb_y + (STATUS_H - F_STATUS.get_height()) // 2
        sc.blit(F_STATUS.render(f'步  {sim.time_step}', True, C_DIM_D), (18, sy))
        sc.blit(F_STATUS.render(f'已转发  {infected}/{len(sim.nodes)}', True, C_DIM_D), (160, sy))
        sc.blit(F_STATUS.render(f'活跃文本  {len(sim.active_texts)}', True, C_DIM_D), (340, sy))
        sc.blit(F_STATUS.render(f'API  {sim.api_calls}', True, C_DIM_D), (500, sy))

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
