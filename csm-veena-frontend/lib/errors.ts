import { toast } from "sonner"

export interface ApiError {
  status: number
  message: string
  code?: string
}

export function handleApiError(error: unknown): ApiError {
  if (error instanceof Error) {
    // Check if it's a custom API error object thrown by our client
    if ("status" in error) {
      return error as unknown as ApiError
    }
    return { status: 500, message: error.message }
  }
  return { status: 500, message: "An unexpected error occurred" }
}

export function showApiErrorToast(error: unknown) {
  const apiError = handleApiError(error)

  let title = "Error"
  let description = apiError.message

  switch (apiError.status) {
    case 400:
      title = "Invalid Request"
      break
    case 401:
      title = "Session Expired"
      description = "Please log in again."
      break
    case 403:
      title = "Access Denied"
      description = "You do not have permission to perform this action."
      break
    case 404:
      title = "Not Found"
      break
    case 409:
      title = "Conflict"
      break
    case 500:
      title = "Server Error"
      description = "Something went wrong on our end. Please try again later."
      break
  }

  toast.error(title, {
    description,
  })
}
