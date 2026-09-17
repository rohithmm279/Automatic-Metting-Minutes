/**
 * API Service Layer for Meeting Minutes FastAPI Backend.
 * Centralizes all HTTP communication with the backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers });

    // 204 No Content has no body
    if (response.status === 204) {
      return null;
    }

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const errorMsg = data?.detail || `HTTP Error ${response.status}: ${response.statusText}`;
      const error = new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      const connErr = new Error(
        `Cannot connect to backend server at ${API_BASE_URL}. Ensure the FastAPI backend is running.`
      );
      connErr.status = 0;
      throw connErr;
    }
    throw err;
  }
}

export const api = {
  /**
   * Health check endpoint
   */
  async getHealth() {
    return request('/health');
  },

  /**
   * Run AI analysis on raw transcript and save meeting
   * @param {string} transcript - The meeting transcript text
   */
  async createMeeting(transcript) {
    return request('/meetings', {
      method: 'POST',
      body: JSON.stringify({ transcript }),
    });
  },

  /**
   * List stored meetings with summary and item counts
   * @param {number} limit - Max records to return
   * @param {number} offset - Pagination offset
   */
  async getMeetings(limit = 50, offset = 0) {
    return request(`/meetings?limit=${limit}&offset=${offset}`);
  },

  /**
   * Retrieve full meeting details including action items, decisions, issues
   * @param {number|string} meetingId - The meeting ID
   */
  async getMeeting(meetingId) {
    return request(`/meetings/${meetingId}`);
  },

  /**
   * Update the status of a specific action item
   * @param {number|string} meetingId - Parent meeting ID
   * @param {number|string} itemId - Action item ID
   * @param {'pending'|'in_progress'|'completed'|'cancelled'} status - New status
   */
  async updateActionItemStatus(meetingId, itemId, status) {
    return request(`/meetings/${meetingId}/action-items/${itemId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },

  /**
   * Delete a meeting and cascade-delete child items
   * @param {number|string} meetingId - Meeting ID to delete
   */
  async deleteMeeting(meetingId) {
    return request(`/meetings/${meetingId}`, {
      method: 'DELETE',
    });
  },
};

export default api;
