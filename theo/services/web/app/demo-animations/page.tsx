"use client";

import { useState } from "react";
import { Spinner, LoadingOverlay } from "../components/LoadingStates";
import ErrorCallout from "../components/ErrorCallout";

export default function AnimationDemoPage() {
  const [showError, setShowError] = useState(false);
  const [errorKey, setErrorKey] = useState(0);
  const [showOverlay, setShowOverlay] = useState(false);

  const triggerError = () => {
    setErrorKey(prev => prev + 1);
    setShowError(true);
  };

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem" }}>
      <header style={{ marginBottom: "3rem" }}>
        <h1 className="fade-in" style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>
          Animation Utilities Demo
        </h1>
        <p className="fade-in" style={{ color: "var(--color-text-muted)" }}>
          Preview all available animation classes in action
        </p>
      </header>

      {/* Entrance Animations */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Entrance Animations</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <div className="card fade-in">
            <strong>fade-in</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Smooth opacity transition</p>
          </div>
          <div className="card slide-up">
            <strong>slide-up</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Slides from below</p>
          </div>
          <div className="card slide-down">
            <strong>slide-down</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Slides from above</p>
          </div>
          <div className="card slide-left">
            <strong>slide-left</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Slides from right</p>
          </div>
          <div className="card slide-right">
            <strong>slide-right</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Slides from left</p>
          </div>
          <div className="card scale-in">
            <strong>scale-in</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Scales up from 95%</p>
          </div>
        </div>
      </section>

      {/* Continuous Animations */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Continuous Animations</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <div className="card" style={{ textAlign: "center" }}>
            <div className="spin" style={{ fontSize: "2rem", marginBottom: "1rem" }}>⟳</div>
            <strong>spin</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Normal speed (1s)</p>
          </div>
          <div className="card" style={{ textAlign: "center" }}>
            <div className="spin-fast" style={{ fontSize: "2rem", marginBottom: "1rem" }}>⟳</div>
            <strong>spin-fast</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Fast rotation (0.6s)</p>
          </div>
          <div className="card" style={{ textAlign: "center" }}>
            <div className="spin-slow" style={{ fontSize: "2rem", marginBottom: "1rem" }}>⟳</div>
            <strong>spin-slow</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Slow rotation (2s)</p>
          </div>
          <div className="card pulse" style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>●</div>
            <strong>pulse</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Opacity pulse (2s)</p>
          </div>
          <div className="card pulse-fast" style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>●</div>
            <strong>pulse-fast</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Fast pulse (1s)</p>
          </div>
          <div className="card shimmer" style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>✨</div>
            <strong>shimmer</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>Shimmer effect</p>
          </div>
        </div>
      </section>

      {/* Special Effects */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Special Effects</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <div className="card">
            <strong>shake</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", marginBottom: "1rem" }}>
              Horizontal shake for errors
            </p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={triggerError}
            >
              Trigger Error
            </button>
          </div>
          <div className="card">
            <strong>bounce</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", marginBottom: "1rem" }}>
              Bouncy scale effect
            </p>
            <button
              type="button"
              className="btn btn-secondary bounce"
            >
              Bouncy Button
            </button>
          </div>
        </div>
      </section>

      {/* Staggered Animations */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Staggered Animations</h2>
        <p style={{ color: "var(--color-text-muted)", marginBottom: "1rem" }}>
          Items appear with incremental delays (50ms each)
        </p>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="card stagger-item">
              <strong>Item {i + 1}</strong>
              <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", margin: 0 }}>
                Delay: {(i + 1) * 50}ms
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Loading Components */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Enhanced Loading Components</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "1rem" }}>
          <div className="card" style={{ textAlign: "center" }}>
            <strong style={{ marginBottom: "1rem", display: "block" }}>Spinner (with spin)</strong>
            <Spinner size="lg" />
          </div>
          <div className="card">
            <strong style={{ marginBottom: "1rem", display: "block" }}>Skeleton (with shimmer)</strong>
            <div className="skeleton shimmer" style={{ height: "1rem", marginBottom: "0.5rem" }} />
            <div className="skeleton shimmer" style={{ height: "1rem", marginBottom: "0.5rem" }} />
            <div className="skeleton shimmer" style={{ height: "1rem", width: "70%" }} />
          </div>
        </div>
        <div style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setShowOverlay(true);
              setTimeout(() => setShowOverlay(false), 3000);
            }}
          >
            Show Loading Overlay (3s)
          </button>
        </div>
      </section>

      {/* Error Demo */}
      {showError && (
        <section style={{ marginBottom: "3rem" }}>
          <ErrorCallout
            key={errorKey}
            message="This is a demo error with shake animation!"
            onRetry={() => {
              setShowError(false);
              setTimeout(() => triggerError(), 100);
            }}
          />
        </section>
      )}

      {/* Combining Animations */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Combining Animations</h2>
        <p style={{ color: "var(--color-text-muted)", marginBottom: "1rem" }}>
          Multiple classes can be combined for complex effects
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <div className="card fade-in slide-up">
            <strong>fade-in slide-up</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
              Fades and slides together
            </p>
          </div>
          <div className="card scale-in pulse">
            <strong>scale-in pulse</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
              Scales in, then pulses
            </p>
          </div>
          <div className="card fade-in shimmer">
            <strong>fade-in shimmer</strong>
            <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
              Fades in with shimmer
            </p>
          </div>
        </div>
      </section>

      {/* Context-Aware Animations */}
      <section style={{ marginBottom: "3rem" }}>
        <h2>Context-Aware Animations</h2>
        <p style={{ color: "var(--color-text-muted)", marginBottom: "1rem" }}>
          Different animations for different contexts
        </p>
        <div style={{ display: "grid", gap: "1rem" }}>
          <div className="alert alert-success bounce">
            <strong>✓ Success!</strong> This alert bounces when it appears
          </div>
          <div className="alert alert-danger shake">
            <strong>✗ Error!</strong> This alert shakes to grab attention
          </div>
          <div className="alert alert-info fade-in">
            <strong>ℹ Info:</strong> This alert fades in smoothly
          </div>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <span className="badge badge-success bounce">Completed</span>
            <span className="badge badge-secondary pulse">Running</span>
            <span className="badge badge-danger">Failed</span>
          </div>
        </div>
      </section>

      {/* Usage Guide */}
      <section style={{ marginBottom: "3rem" }}>
        <div className="card" style={{ background: "var(--color-surface-muted)" }}>
          <h3>Usage</h3>
          <p style={{ color: "var(--color-text-muted)" }}>
            Simply add the class name to any element:
          </p>
          <pre style={{
            background: "var(--color-surface)",
            padding: "1rem",
            borderRadius: "0.5rem",
            overflow: "auto",
            fontSize: "0.875rem"
          }}>
{`<div className="fade-in">Content</div>
<div className="stagger-item">Item 1</div>
<div className="spin">⟳</div>
<ErrorCallout /> {/* Auto-shake on error */}

// Context-aware
<div className="alert alert-success bounce">Success!</div>
<div className="alert alert-danger shake">Error!</div>
<span className="badge pulse">Running</span>`}
          </pre>
          <p style={{ color: "var(--color-text-muted)", marginTop: "1rem", marginBottom: 0 }}>
            All animations respect <code>prefers-reduced-motion</code> for accessibility.
          </p>
        </div>
      </section>

      {showOverlay && <LoadingOverlay message="Loading demo content..." />}
    </div>
  );
}
