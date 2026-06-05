"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const form = new FormData(e.currentTarget);
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usr: form.get("usr"),
        pwd: form.get("pwd"),
      }),
    });

    setLoading(false);

    if (res.ok) {
      router.push("/dashboard");
    } else {
      const body = await res.json().catch(() => ({}));
      setError(body.error ?? "Login failed");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0B1220] px-4">
      <div className="w-full max-w-sm bg-[#111A2E] rounded-2xl border border-[#1E2D45] shadow-xl p-8">
        {/* Logo */}
        <div className="mb-6">
          <h1 className="font-bold text-2xl tracking-widest">
            <span style={{ color: "#22D38C" }}>NET</span>
            <span style={{ color: "#E6EDF7" }}>GAIN</span>
            <span style={{ color: "#22D38C" }}>Z</span>
          </h1>
          <p className="text-sm mt-1" style={{ color: "#8A97B2" }}>Sign in to your gym account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="usr"
              className="block text-xs uppercase tracking-wider mb-1"
              style={{ color: "#8A97B2" }}
            >
              Username
            </label>
            <input
              id="usr"
              name="usr"
              type="text"
              required
              autoComplete="username"
              placeholder="Administrator"
              className="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C]"
            />
          </div>

          <div>
            <label
              htmlFor="pwd"
              className="block text-xs uppercase tracking-wider mb-1"
              style={{ color: "#8A97B2" }}
            >
              Password
            </label>
            <input
              id="pwd"
              name="pwd"
              type="password"
              required
              autoComplete="current-password"
              className="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C]"
            />
          </div>

          {error && (
            <p className="text-sm text-[#F87171]">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
