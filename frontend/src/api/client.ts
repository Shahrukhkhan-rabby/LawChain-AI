import axios from 'axios';

/** Development JWT signed with the project JWT_SECRET — valid for 1 year. */
export const DEV_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXYtdXNlci0wMDEiLCJlbWFpbCI6ImRldkBsYXdjaGFpbi5haSIsInJvbGVzIjpbImxhd3llciJdLCJleHAiOjE4MDkzMzE4MDB9.MWEKvjBv33bwgPY4qCkbJf9Ma5vS9NXhLPZgn-2e4IA';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Attach (or remove) the JWT bearer token on all subsequent requests.
 */
export function setAuthToken(token: string | null): void {
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
}

// Automatically authenticate with the dev token on import.
setAuthToken(DEV_TOKEN);

export default apiClient;
