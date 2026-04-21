import { useEffect, useState } from 'react'

const THEME_KEY = 'feihualing:theme'
const BGM_ENABLED_KEY = 'feihualing:bgm:enabled'
const BGM_VOLUME_KEY = 'feihualing:bgm:volume'

type Theme = 'light' | 'dark' | 'system'

function Section({
  title,
  description,
  wip,
  children,
}: {
  title: string
  description?: string
  wip?: boolean
  children: React.ReactNode
}) {
  return (
    <section className="settings-section">
      <header className="settings-section-header">
        <h2>
          {title}
          {wip ? <span className="settings-wip-tag">开发中</span> : null}
        </h2>
        {description ? <p className="settings-section-desc">{description}</p> : null}
      </header>
      <div className="settings-section-body">{children}</div>
    </section>
  )
}

export function SettingsPage() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'system'
    return (window.localStorage.getItem(THEME_KEY) as Theme) || 'system'
  })
  const [bgmEnabled, setBgmEnabled] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(BGM_ENABLED_KEY) === '1'
  })
  const [bgmVolume, setBgmVolume] = useState(() => {
    if (typeof window === 'undefined') return 40
    const raw = window.localStorage.getItem(BGM_VOLUME_KEY)
    return raw ? Number(raw) : 40
  })

  useEffect(() => {
    window.localStorage.setItem(THEME_KEY, theme)
  }, [theme])
  useEffect(() => {
    window.localStorage.setItem(BGM_ENABLED_KEY, bgmEnabled ? '1' : '0')
  }, [bgmEnabled])
  useEffect(() => {
    window.localStorage.setItem(BGM_VOLUME_KEY, String(bgmVolume))
  }, [bgmVolume])

  return (
    <div className="settings-page">
      <Section
        title="大模型接入"
        description="后期支持自定义对话模型 base_url、API key、模型名。当前后端使用 DashScope qwen-plus（OpenAI 兼容模式）。"
        wip
      >
        <div className="settings-form">
          <label className="settings-field">
            <span>Provider</span>
            <select className="settings-input" disabled defaultValue="dashscope">
              <option value="dashscope">阿里百炼 DashScope</option>
              <option value="openai">OpenAI</option>
              <option value="claude">Anthropic Claude</option>
              <option value="ollama">Ollama 本地</option>
              <option value="custom">自定义 OpenAI 兼容</option>
            </select>
          </label>
          <label className="settings-field">
            <span>Base URL</span>
            <input className="settings-input" disabled placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </label>
          <label className="settings-field">
            <span>API Key</span>
            <input className="settings-input" type="password" disabled placeholder="sk-xxxxxxx（存在浏览器本地，不上传服务器）" />
          </label>
          <label className="settings-field">
            <span>Model</span>
            <input className="settings-input" disabled placeholder="qwen-plus" />
          </label>
        </div>
      </Section>

      <Section
        title="嵌入模型接入"
        description="后期支持切换 embedding provider。当前使用本机 Ollama bge-large-zh-v1.5（1024 维）。"
        wip
      >
        <div className="settings-form">
          <label className="settings-field">
            <span>Provider</span>
            <select className="settings-input" disabled defaultValue="ollama">
              <option value="ollama">Ollama 本地</option>
              <option value="dashscope">阿里百炼 text-embedding</option>
              <option value="openai">OpenAI text-embedding-3-small</option>
            </select>
          </label>
          <label className="settings-field">
            <span>Base URL</span>
            <input className="settings-input" disabled placeholder="http://localhost:11434" />
          </label>
          <label className="settings-field">
            <span>Model</span>
            <input className="settings-input" disabled placeholder="quentinz/bge-large-zh-v1.5" />
          </label>
          <p className="settings-hint">
            切换 embedding 模型会改变向量维度，需要重跑 `backfill_embeddings` 重算所有数据。
          </p>
        </div>
      </Section>

      <Section
        title="主题"
        description="浅色、深色、跟随系统。"
        wip
      >
        <div className="settings-theme">
          {(['light', 'dark', 'system'] as Theme[]).map((value) => (
            <button
              key={value}
              type="button"
              className={theme === value ? 'settings-theme-btn settings-theme-btn-active' : 'settings-theme-btn'}
              onClick={() => setTheme(value)}
            >
              {value === 'light' ? '浅色' : value === 'dark' ? '深色' : '跟随系统'}
            </button>
          ))}
        </div>
        <p className="settings-hint">当前仅保存偏好，主题切换视觉尚未实现。</p>
      </Section>

      <Section
        title="背景音乐"
        description="对局时播放古风配乐。"
        wip
      >
        <div className="settings-form">
          <label className="settings-switch-row">
            <span>启用背景音乐</span>
            <button
              type="button"
              role="switch"
              aria-checked={bgmEnabled}
              className={bgmEnabled ? 'settings-switch settings-switch-on' : 'settings-switch'}
              onClick={() => setBgmEnabled((v) => !v)}
            >
              <span className="settings-switch-knob" />
            </button>
          </label>
          <label className="settings-field">
            <span>音量（{bgmVolume}%）</span>
            <input
              className="settings-range"
              type="range"
              min={0}
              max={100}
              value={bgmVolume}
              onChange={(event) => setBgmVolume(Number(event.target.value))}
              disabled={!bgmEnabled}
            />
          </label>
          <p className="settings-hint">偏好已保存到本地，播放器尚未实现。</p>
        </div>
      </Section>

      <Section title="关于" description="飞花令 v0.1 · 本地开发版本">
        <ul className="settings-info">
          <li>
            后端：FastAPI · Postgres 16 · pgvector · zhparser · Ollama bge-large-zh · qwen-plus
          </li>
          <li>前端：React 19 · React Router v6 · TanStack Query · Vite</li>
          <li>当前主要功能：诗词管理、RAG Hybrid 检索、文档切分向量化、飞花令 Agent</li>
        </ul>
      </Section>
    </div>
  )
}
