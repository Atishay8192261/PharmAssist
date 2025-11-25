"use client"

import type React from "react"

import { useState } from "react"
import { api } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const response = await api.login({ username, password })
      login(response.access_token)
    } catch (err: any) {
      setError(err.message || "Login failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">PharmAssist</CardTitle>
          <CardDescription className="text-center">Sign in to access your account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                disabled={loading}
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign In"}
            </Button>
            <div className="pt-2">
              <OAuthGoogleButton />
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

function OAuthGoogleButton() {
  const { login } = useAuth()
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID
  const redirectUri = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_REDIRECT_URI
  const scope = "openid email profile"

  if (!clientId || !redirectUri) {
    return (
      <Alert variant="default">
        <AlertDescription>Google OAuth not configured</AlertDescription>
      </Alert>
    )
  }

  const start = async () => {
    setErr(null)
    setLoading(true)
    try {
      // PKCE code verifier & challenge
      const verifierBytes = crypto.getRandomValues(new Uint8Array(64))
      const verifier = btoa(String.fromCharCode(...verifierBytes))
        .replace(/[^a-zA-Z0-9]/g, "")
        .slice(0, 64) // sanitize length
      const encoder = new TextEncoder()
      const challengeData = await crypto.subtle.digest("SHA-256", encoder.encode(verifier))
      const challengeArray = Array.from(new Uint8Array(challengeData))
      const challenge = btoa(String.fromCharCode(...challengeArray))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "")
      sessionStorage.setItem("oauth_code_verifier", verifier)
      const state = crypto.randomUUID()
      sessionStorage.setItem("oauth_state", state)
      const authUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth")
      authUrl.searchParams.set("client_id", clientId)
      authUrl.searchParams.set("redirect_uri", redirectUri)
      authUrl.searchParams.set("response_type", "code")
      authUrl.searchParams.set("scope", scope)
      authUrl.searchParams.set("code_challenge", challenge)
      authUrl.searchParams.set("code_challenge_method", "S256")
      authUrl.searchParams.set("access_type", "offline")
      authUrl.searchParams.set("prompt", "consent")
      authUrl.searchParams.set("state", state)
      window.location.href = authUrl.toString()
    } catch (e: any) {
      setErr(e.message || "OAuth start failed")
      setLoading(false)
    }
  }

  return (
    <div className="space-y-2">
      {err && (
        <Alert variant="destructive">
          <AlertDescription>{err}</AlertDescription>
        </Alert>
      )}
      <Button type="button" variant="outline" className="w-full" disabled={loading} onClick={start}>
        {loading ? "Redirecting..." : "Continue with Google"}
      </Button>
    </div>
  )
}
