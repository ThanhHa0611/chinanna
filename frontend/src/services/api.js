const API_BASE = import.meta.env.VITE_API_URL || '';

async function request(endpoint, options = {}) {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(', ')
      : detail ||
        (response.status === 404
          ? 'API chưa sẵn sàng. Hãy khởi động lại backend (đóng hết cửa sổ server cũ rồi chạy start.bat).'
          : `Có lỗi xảy ra (HTTP ${response.status})`);
    throw new Error(message);
  }

  return data;
}

export const api = {
  register: (body) =>
    request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  login: (body) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getMe: () => request('/api/auth/me'),

  updateProfile: (body) =>
    request('/api/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  changePassword: (body) =>
    request('/api/auth/password', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  logout: () => request('/api/auth/logout', { method: 'POST' }),

  requestForgotPasswordOtp: (email) =>
    request('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPasswordWithOtp: (body) =>
    request('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getFeedback: () => request('/api/feedback'),

  submitFeedback: (body) =>
    request('/api/feedback', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  replyFeedback: (feedbackId, body) =>
    request(`/api/feedback/${feedbackId}/reply`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  ackFeedback: (feedbackId) =>
    request(`/api/feedback/${feedbackId}/ack`, { method: 'POST' }),

  deleteFeedback: (feedbackId) =>
    request(`/api/feedback/${feedbackId}`, { method: 'DELETE' }),

  getPersonalDeclaration: () => request('/api/documents/personal-declaration'),

  openPersonalDeclaration: () =>
    request('/api/documents/personal-declaration', { method: 'POST' }),

  registerPersonalDeclarationLink: (body) =>
    request('/api/documents/personal-declaration', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  openPersonalDeclarationFile: async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/api/documents/personal-declaration/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Không mở được file (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  getParentChild: () => request('/api/parent/child'),

  openParentChildDocumentFile: async (docId) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/api/parent/child/documents/${docId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Không mở được file (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  getApplyDocuments: () => request('/api/documents/apply'),

  ackDocumentFeedback: (docId) =>
    request(`/api/documents/apply/${docId}/ack-feedback`, { method: 'POST' }),

  ackDocumentUpload: (docId) =>
    request(`/api/documents/apply/${docId}/ack-upload`, { method: 'POST' }),

  ackMissingDocumentsReminder: () =>
    request('/api/documents/apply/ack-missing-reminder', { method: 'POST' }),

  ackProfileInfoReminder: () =>
    request('/api/auth/ack-profile-reminder', { method: 'POST' }),

  uploadApplyDocument: async (docId, file) => {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/api/documents/apply/${docId}/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Có lỗi xảy ra (HTTP ${response.status})`);
    }
    return data;
  },

  updateLanguageScores: (body) =>
    request('/api/documents/apply/language/scores', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  submitLanguageScoreUpdate: (body) =>
    request('/api/documents/apply/language/score-update', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  setLanguageMentorHandles: (body) =>
    request('/api/documents/apply/language/mentor-handles', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  setApplyDocumentMenteeRequest: (docId, body) =>
    request(`/api/documents/apply/${docId}/mentee-request`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  updatePreferredSchoolsNote: (body) =>
    request('/api/documents/apply/preferred-schools-note', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getApplyProgress: () => request('/api/documents/apply-progress'),

  ackApplyProgress: () =>
    request('/api/documents/apply-progress/ack', { method: 'POST' }),

  updateApplyProgress: (body) =>
    request('/api/documents/apply-progress', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  getHdnkNckh: () => request('/api/documents/hdnk-nckh'),

  updateHdnkNckh: (body) =>
    request('/api/documents/hdnk-nckh', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  openApplyDocumentFile: async (docId) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/api/documents/apply/${docId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Không mở được file (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },

  downloadApplyDocument: async (docId, filename = 'document') => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/api/documents/apply/${docId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Không tải được file (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  },
};
