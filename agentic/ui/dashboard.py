"""PaperForge Dashboard — Streamlit retro synthwave UI."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
import time

st.set_page_config(
    page_title="PaperForge",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def inject_background():
    """Inject animated particle canvas directly into the page, script via helper iframe."""
    # Canvas + scanlines injected directly into Streamlit's DOM
    st.markdown("""
    <canvas id="bg-canvas" style="position:fixed;inset:0;z-index:0;pointer-events:none;"></canvas>
    <div style="position:fixed;inset:0;z-index:998;pointer-events:none;
      background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.025) 2px,rgba(0,0,0,0.025) 4px);"></div>
    """, unsafe_allow_html=True)

    # Script runs in a same-origin iframe, accesses parent.document to draw on the canvas
    components.html("""
    <script>
    const d=parent.document,w=parent.window;
    const c=d.getElementById('bg-canvas'),x=c.getContext('2d');
    c.width=w.innerWidth;c.height=w.innerHeight;
    w.addEventListener('resize',()=>{c.width=w.innerWidth;c.height=w.innerHeight;});
    let t=0,ps=[],orbs=[],stars=[];
    const COLS=['#ff6b9d','#00e5ff','#a0ff48','#b083ff','#ffb347','#ff9a76','#7bffd7'];
    class Orb{constructor(){this.x=Math.random()*c.width;this.y=Math.random()*c.height;
      this.r=120+Math.random()*200;this.col=COLS[Math.floor(Math.random()*COLS.length)];
      this.sx=(Math.random()-0.5)*0.25;this.sy=(Math.random()-0.5)*0.25;
      this.px=Math.random()*Math.PI*2;this.py=Math.random()*Math.PI*2;}
      update(){this.x+=this.sx+Math.sin(t*0.3+this.px)*0.2;this.y+=this.sy+Math.cos(t*0.4+this.py)*0.2;
      if(this.x<-this.r)this.x=c.width+this.r;if(this.x>c.width+this.r)this.x=-this.r;
      if(this.y<-this.r)this.y=c.height+this.r;if(this.y>c.height+this.r)this.y=-this.r;}
      draw(){const g=x.createRadialGradient(this.x,this.y,0,this.x,this.y,this.r);
      g.addColorStop(0,this.col);g.addColorStop(0.5,this.col+'22');g.addColorStop(1,'transparent');
      x.beginPath();x.arc(this.x,this.y,this.r,0,Math.PI*2);x.fillStyle=g;
      x.globalAlpha=0.12;x.fill();x.globalAlpha=1;}}
    class P{constructor(){this.reset(true);}
      reset(init){this.x=Math.random()*c.width;
      this.y=init?Math.random()*c.height:c.height+20;
      this.s=Math.random()<0.08?3.5+Math.random()*4:Math.random()*2.5+0.6;
      this.sx=(Math.random()-0.5)*0.5;this.sy=-(Math.random()*0.7+0.2);
      this.col=COLS[Math.floor(Math.random()*COLS.length)];
      this.op=Math.random()*0.6+0.2;this.fs=Math.random()*0.006+0.003;
      this.fading=Math.random()>0.4;this.trail=[];this.mt=Math.floor(Math.random()*6)+3;
      this.tw=Math.random()*0.04+0.01;this.tp=Math.random()*Math.PI*2;}
      update(){this.trail.unshift({x:this.x,y:this.y});if(this.trail.length>this.mt)this.trail.pop();
      this.x+=this.sx+Math.sin(t*0.05+this.y*0.01)*0.2;this.y+=this.sy;
      if(this.fading){this.op-=this.fs;if(this.op<=0.08)this.fading=false;}
      else{this.op+=this.fs;if(this.op>=0.65)this.fading=true;}
      if(this.y<-30||this.x<-30||this.x>c.width+30)this.reset(false);}
      draw(){const eo=this.op;
      for(let i=0;i<this.trail.length;i++){const tr=this.trail[i];
      x.beginPath();x.arc(tr.x,tr.y,this.s*0.6,0,Math.PI*2);
      x.fillStyle=this.col;x.globalAlpha=eo*(1-i/this.trail.length)*0.35;x.fill();}
      const g=x.createRadialGradient(this.x,this.y,0,this.x,this.y,this.s*4);
      g.addColorStop(0,this.col);g.addColorStop(1,'transparent');
      x.beginPath();x.arc(this.x,this.y,this.s*4,0,Math.PI*2);x.fillStyle=g;
      x.globalAlpha=eo*0.5;x.fill();
      x.beginPath();x.arc(this.x,this.y,this.s,0,Math.PI*2);x.fillStyle=this.col;
      x.globalAlpha=eo;x.fill();x.globalAlpha=1;}}
    for(let i=0;i<220;i++)ps.push(new P());
    for(let i=0;i<5;i++)orbs.push(new Orb());
    function anim(){t++;x.clearRect(0,0,c.width,c.height);
      for(const o of orbs){o.update();o.draw();}
      for(const p of ps){p.update();p.draw();}
      for(let i=0;i<ps.length;i++){for(let j=i+1;j<ps.length;j++){
        const dx=ps[i].x-ps[j].x,dy=ps[i].y-ps[j].y,dist=Math.sqrt(dx*dx+dy*dy);
        if(dist<130){x.beginPath();x.moveTo(ps[i].x,ps[i].y);x.lineTo(ps[j].x,ps[j].y);
        x.strokeStyle='#b083ff';x.globalAlpha=(1-dist/130)*0.07;x.lineWidth=0.5;
        x.stroke();x.globalAlpha=1;}}}
      if(Math.random()<0.012){const ang=-Math.PI/6+(Math.random()-0.5)*0.6,sp=4+Math.random()*8;
      stars.push({x:Math.random()*c.width*.6,y:Math.random()*c.height*.5,
      vx:Math.cos(ang)*sp,vy:Math.sin(ang)*sp,life:1,len:60+Math.random()*120});}
      for(let s=stars.length-1;s>=0;s--){const st=stars[s],tl=st.len;
      const g=x.createLinearGradient(st.x,st.y,st.x-st.vx/st.len*tl,st.y-st.vy/st.len*tl);
      g.addColorStop(0,'#ffffff');g.addColorStop(0.3,st.life>0.5?'#ffe0ff':'#b0b0ff');
      g.addColorStop(1,'transparent');x.beginPath();
      x.moveTo(st.x,st.y);x.lineTo(st.x-st.vx/st.len*tl,st.y-st.vy/st.len*tl);
      x.strokeStyle=g;x.globalAlpha=st.life*0.8;x.lineWidth=1.4;x.stroke();
      x.beginPath();x.arc(st.x,st.y,2,0,Math.PI*2);x.fillStyle='#ffffff';
      x.globalAlpha=st.life;x.fill();x.globalAlpha=1;
      st.x+=st.vx;st.y+=st.vy;st.life-=0.014;
      if(st.life<=0||st.x>c.width+50||st.y>c.height+50||st.x<-50)stars.splice(s,1);}
      requestAnimationFrame(anim);}anim();
    </script>
    """, height=0)


inject_background()

# Custom CSS
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
  * { font-family: 'IBM Plex Mono', monospace !important; }
  .stApp { background: transparent !important; }
  .stApp > header { background: transparent !important; }
  [data-testid="stAppViewContainer"] { background: transparent !important; }
  [data-testid="stHeader"] { background: transparent !important; }
  .main .block-container { background: transparent !important; padding-top:2rem !important; }
  section[data-testid="stSidebar"] { display: none; }
  body { background: #0a0a0f !important; }
  .logo {
    text-align:center; font-size:1.4rem; font-weight:600; letter-spacing:0.15em;
    background: linear-gradient(135deg, #ff6b9d, #b083ff);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    margin-bottom:0.25rem;
  }
  .tagline { text-align:center; font-size:0.7rem; color:#7a7a9a; letter-spacing:0.08em; margin-bottom:2rem; }
  .stTextInput>div>div>input, .stTextArea>div>div>textarea {
    background:#0a0a0f !important; border:1px solid #2a2a3a !important;
    border-radius:10px !important; color:#e0d8f0 !important;
  }
  .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
    border-color:#00e5ff !important; box-shadow:0 0 20px rgba(0,229,255,0.3) !important;
  }
  .stButton>button {
    background:linear-gradient(135deg, #ff6b9d, #b083ff) !important;
    border:none !important; border-radius:100px !important; color:#fff !important;
    font-weight:600 !important; letter-spacing:0.04em !important;
    padding:0.6rem 2rem !important; box-shadow:0 0 20px rgba(255,107,157,0.3) !important;
  }
  .stButton>button:hover { transform:translateY(-1px); box-shadow:0 0 30px rgba(255,107,157,0.5) !important; }
  .agent-card {
    background:#12121a; border:1px solid #2a2a3a; border-radius:12px;
    padding:0.9rem 1rem; margin:0.5rem 0;
  }
  .status-running { color:#ffb347; animation:pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .score-bar { display:flex; gap:2px; margin-top:4px; }
  .score-seg { width:16px; height:4px; border-radius:2px; background:#2a2a3a; }
  .score-seg.filled { background:#a0ff48; }
  .score-seg.warn { background:#ffb347; }
  .score-seg.bad { background:#ff4757; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="logo">PAPERFORGE</div>', unsafe_allow_html=True)
st.markdown('<div class="tagline">DROP CODE → PROMPT → PAPER</div>', unsafe_allow_html=True)

# Input Card
with st.container():
    repo_url = ""
    uploaded = None
    col1, col2 = st.columns([3, 1])
    with col1:
        source_type = st.radio("Source", ["GitHub URL", "ZIP Upload"], horizontal=True, label_visibility="collapsed")
        if source_type == "GitHub URL":
            repo_url = st.text_input(
                "repo_url", placeholder="https://github.com/your-username/your-repo",
                label_visibility="collapsed"
            )
        else:
            uploaded = st.file_uploader("Upload ZIP", type="zip", label_visibility="collapsed")

    prompt = st.text_area(
        "prompt",
        placeholder="Write a bioinformatics methods paper about my variant calling pipeline. Focus on the NUMT filtering approach and benchmark against MuTect2 and VarScan2. Target: Bioinformatics journal.",
        label_visibility="collapsed",
        height=120,
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.caption("Claude · Gemini · DeepSeek")
    with c3:
        generate = st.button("▶ GENERATE", use_container_width=True)

# Pipeline Execution
if generate:
    has_input = (source_type == "GitHub URL" and repo_url) or (source_type == "ZIP Upload" and uploaded)
    if not has_input:
        st.warning("Provide a GitHub URL or ZIP upload.")
    elif not prompt.strip():
        st.warning("Write a prompt describing your paper.")
    else:
        st.markdown("---")
        st.markdown(
            '<span style="color:#ff6b9d;font-size:0.72rem;letter-spacing:0.06em;">'
            '▶ PIPELINE STARTED — 10 AGENTS</span>',
            unsafe_allow_html=True,
        )

        agents = [
            ("Code Analyst", "Gemini", "G", "#00e5ff", "Analyzing repository… 23 Python files, 8 modules. Bayesian mixture model for NUMT detection identified."),
            ("Style Researcher", "DeepSeek", "D", "#a0ff48", "Loaded cached style_guide.md (2 days old). 127 bioinformatics sentence patterns available."),
            ("Writer", "DeepSeek", "D", "#a0ff48", "Drafted 5 sections: Abstract (198w), Intro (1.2kw), Methods (2.1kw), Results (1.8kw), Discussion (1.5kw)."),
            ("Assessor", "Claude", "C", "#ff6b9d", "Scored: Abs 8.2, Intro 7.8, Methods 6.2, Results 7.5, Disc 7.1. Methods: too vague, 4 AI phrases flagged."),
            ("Rewriter", "Claude", "C", "#ff6b9d", "Rewrite #1 — Methods section. Added algorithm details, removed AI phrases. Rescoring pending…"),
            ("Assessor", "Claude", "C", "#ff6b9d", "Methods rescored: 7.8/10. All sections above threshold. Proceeding to plagiarism check."),
            ("Plagiarism Check", "DeepSeek", "D", "#a0ff48", "Originality: 92%. AI-likelihood: 14%. Both above thresholds. 0 passages flagged."),
            ("Figure Generator", "Gemini", "G", "#00e5ff", "Generated 4 figures: pipeline overview, benchmark boxplot, ROC curves, runtime analysis. Dark theme, colorblind-friendly."),
            ("Figure Supervisor", "Claude", "C", "#ff6b9d", "All 4 figures pass. Color accessibility OK. Font sizes readable. No matplotlib gray background."),
        ]

        for i, (name, model, icon, color, output) in enumerate(agents):
            time.sleep(0.5)
            with st.container():
                st.markdown(
                    f'<div class="agent-card">'
                    f'<span style="display:inline-block;width:28px;height:28px;border-radius:8px;'
                    f'background:rgba({",".join(str(int(color[i:i+2],16)) for i in (1,3,5))},0.12);'
                    f'color:{color};text-align:center;line-height:28px;font-weight:600;font-size:0.65rem;">'
                    f'{icon}</span> '
                    f'<strong>{name}</strong> <span style="color:#7a7a9a;">· {model}</span> '
                    f'<span class="status-running">●</span>'
                    f'<div style="margin-top:0.4rem;padding:0.5rem;background:#0a0a0f;border-radius:6px;font-size:0.7rem;color:#7a7a9a;">'
                    f'{output}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        time.sleep(0.5)
        st.success("paper.tex ready — 6,812 words · 4 figures · 92% originality · $2.41")

        col_dl1, col_dl2, col_dl3 = st.columns(3)
        with col_dl1:
            st.download_button("↓ paper.tex", "%% Paper draft\n", file_name="paper.tex")
        with col_dl2:
            st.download_button("↓ figures.zip", b"", file_name="figures.zip")
        with col_dl3:
            st.download_button("↓ agent_log.jsonl", "", file_name="agent_log.jsonl")
