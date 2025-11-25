"use client"
import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useAuth } from "@/context/auth-context"
import { api } from "@/lib/api"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

export default function GoogleCallbackPage() {
  const params = useSearchParams()
  const { login } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const run = async () => {
      const code = params.get("code")
      const state = params.get("state")
      if (!code) {
        setError("Missing authorization code")
        setLoading(false)
        return
      }
      const storedState = sessionStorage.getItem("oauth_state")
      if (!storedState || storedState !== state) {
        setError("State mismatch – potential CSRF")
        setLoading(false)
        return
      }
      const verifier = sessionStorage.getItem("oauth_code_verifier")
      if (!verifier) {
        setError("Missing PKCE verifier – restart login")
        setLoading(false)
        return
      }
      try {
        const resp = await api.exchangeGoogleOAuth(code, verifier)
        if (!resp.access_token) {
          throw new Error((resp as any).error || "OAuth exchange failed")
        }
        // Cleanup sensitive PKCE artifacts from sessionStorage
        sessionStorage.removeItem("oauth_state")
        sessionStorage.removeItem("oauth_code_verifier")
        login(resp.access_token)
      } catch (e: any) {
        setError(e.message || "OAuth error")
        setLoading(false)
        return
      }
      setLoading(false)
      // Redirect based on role encoded in JWT (handled in login in AuthContext)
    }
    run()
  }, [params, login])

  const retry = () => {
    router.push("/login")
  }

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">Exchanging code...</div>
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md space-y-4">
          <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
          <Button onClick={retry} className="w-full">Back to Login</Button>
        </div>
      </div>
    )
  }

  return <div className="flex min-h-screen items-center justify-center">Login successful. Redirecting...</div>
}
