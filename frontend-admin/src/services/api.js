const API_BASE = import.meta.env.VITE_API_URL || '';

function parseDownloadFilename(response, fallback) {
  const customName = response.headers.get('X-Download-Filename');
  if (customName) {
    try {
      return decodeURIComponent(customName);
    } catch {
      return customName;
    }
  }

  const disposition = response.headers.get('Content-Disposition') || '';
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;\n]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const quotedMatch = disposition.match(/filename="([^"]+)"/i);
  if (quotedMatch) {
    return quotedMatch[1];
  }

  const plainMatch = disposition.match(/filename=([^;\n]+)/i);
  if (plainMatch) {
    return plainMatch[1].replace(/"/g, '').trim();
  }

  return fallback;
}

async function downloadBinary(url, fallbackName) {
  const token = localStorage.getItem('admin_token');
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Không tải được file');
  }
  const blob = await response.blob();
  const filename = parseDownloadFilename(response, fallbackName);
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
  return filename;
}

async function request(endpoint, options = {}) {
  const token = localStorage.getItem('admin_token');
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
      : detail || data.message || `Có lỗi xảy ra (HTTP ${response.status})`;
    throw new Error(message);
  }

  return data;
}

export function getActivityAdmins() {
  return request('/api/admin/activities/admins');
}

export function getActivities(adminId) {
  return request(
    adminId
      ? `/api/admin/activities?admin_id=${encodeURIComponent(adminId)}`
      : '/api/admin/activities',
  );
}

export const api = {
  login: (body) =>
    request('/api/admin/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  autoLogin: (body) =>
    request('/api/admin/auth/auto-login', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  register: (body) =>
    request('/api/admin/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getMe: () => request('/api/admin/auth/me'),

  logout: () => request('/api/admin/auth/logout', { method: 'POST' }),

  requestForgotPasswordOtp: (email) =>
    request('/api/admin/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPasswordWithOtp: (body) =>
    request('/api/admin/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  changePassword: (body) =>
    request('/api/admin/auth/password', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getStats: () => request('/api/admin/stats'),

  getInbox: () => request('/api/admin/inbox'),

  getInboxArchiveDay: (dateKey) =>
    request(`/api/admin/inbox/archive/${encodeURIComponent(dateKey)}`),

  confirmInboxTask: (taskId) =>
    request(`/api/admin/inbox/${taskId}/confirm`, { method: 'POST' }),

  bulkConfirmInboxTasks: (taskIds) =>
    request('/api/admin/inbox/bulk-confirm', {
      method: 'POST',
      body: JSON.stringify({ task_ids: taskIds }),
    }),

  viewInboxTask: (taskId) =>
    request(`/api/admin/inbox/${taskId}/view`, { method: 'POST' }),

  updateInboxReminder: (taskId, payload) =>
    request(`/api/admin/inbox/${taskId}/reminder`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  getMentees: () => request('/api/admin/mentees'),

  getMentee: (id) => request(`/api/admin/mentees/${id}`),

  fetchMenteeAvatarObjectUrl: async (menteeId) => {
    const token = localStorage.getItem('admin_token');
    const response = await fetch(`${API_BASE}/api/admin/mentees/${menteeId}/avatar`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Không tải được ảnh đại diện (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  deleteMentee: (id) =>
    request(`/api/admin/mentees/${id}`, {
      method: 'DELETE',
    }),

  getMenteeFeedback: (menteeId) => request(`/api/admin/mentees/${menteeId}/feedback`),

  markMenteeFeedbackRead: (menteeId) =>
    request(`/api/admin/mentees/${menteeId}/feedback/mark-read`, { method: 'POST' }),

  markMenteeDocumentViewed: (menteeId, docId) =>
    request(`/api/admin/mentees/${menteeId}/documents/${docId}/view`, {
      method: 'POST',
    }),

  markMenteeDocumentProcessed: (menteeId, docId) =>
    request(`/api/admin/mentees/${menteeId}/documents/${docId}/process`, {
      method: 'POST',
    }),

  scheduleMenteeDocumentProcess: (menteeId, docId, body) =>
    request(`/api/admin/mentees/${menteeId}/documents/${docId}/schedule`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  ackPreferredSchoolsNote: (menteeId) =>
    request(`/api/admin/mentees/${menteeId}/preferred-schools-note/ack`, {
      method: 'POST',
    }),

  resolveInboxFileUrl(viewUrl) {
    if (!viewUrl) {
      return '';
    }
    try {
      const parsed = new URL(viewUrl, window.location.origin);
      const token = parsed.searchParams.get('token');
      if (token) {
        return `${API_BASE}/api/email/inbox/file?token=${encodeURIComponent(token)}`;
      }
      if (parsed.pathname.includes('/api/email/inbox/file')) {
        return `${API_BASE}${parsed.pathname}${parsed.search}`;
      }
      if (parsed.pathname.includes('/api/email/inbox/view')) {
        return `${API_BASE}${parsed.pathname.replace('/view', '/file')}${parsed.search}`;
      }
    } catch {
      // Fall through to string replacement below.
    }
    const rewritten = viewUrl.replace('/inbox/view', '/inbox/file').replace('/view?', '/file?');
    if (rewritten.startsWith('http')) {
      try {
        const parsed = new URL(rewritten);
        if (parsed.pathname.startsWith('/api/')) {
          return `${API_BASE}${parsed.pathname}${parsed.search}`;
        }
      } catch {
        return rewritten;
      }
    }
    return rewritten.startsWith('/') ? `${API_BASE}${rewritten}` : rewritten;
  },

  async fetchInboxFileFromViewUrl(viewUrl) {
    if (!viewUrl) {
      throw new Error('Không có file để xem');
    }
    const fileUrl = this.resolveInboxFileUrl(viewUrl);
    const response = await fetch(fileUrl);
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new Error(text.includes('Không') ? 'Không mở được file' : 'Không mở được file');
    }
    const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
    if (contentType.includes('text/html')) {
      throw new Error('Không mở được file');
    }
    const blob = await response.blob();
    return {
      url: URL.createObjectURL(blob),
      mimeType: blob.type || response.headers.get('Content-Type') || 'application/pdf',
    };
  },

  async fetchInboxTaskDocumentPreview(taskId) {
    const token = localStorage.getItem('admin_token');
    const response = await fetch(`${API_BASE}/api/admin/inbox/${taskId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Không mở được file');
    }
    const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
    if (contentType.includes('text/html')) {
      throw new Error('Không mở được file');
    }
    const blob = await response.blob();
    return {
      url: URL.createObjectURL(blob),
      mimeType: blob.type || response.headers.get('Content-Type') || 'application/pdf',
    };
  },

  async fetchInboxDocumentPreview(item) {
    const taskId = (item?.id || '').trim();
    const docId = (item?.doc_id || '').trim();
    const menteeId = (item?.mentee_id || '').trim();
    const inboxFileUrl = (item?.file_url || item?.view_url || '').trim();

    if (docId === 'personal-declaration' && menteeId) {
      return this.fetchMenteeDocumentPreview(menteeId, docId);
    }

    const attempts = [];
    if (taskId) {
      attempts.push(() => this.fetchInboxTaskDocumentPreview(taskId));
    }
    if (menteeId && docId) {
      attempts.push(() => this.fetchMenteeDocumentPreview(menteeId, docId));
    }
    if (inboxFileUrl) {
      attempts.push(() => this.fetchInboxFileFromViewUrl(inboxFileUrl));
    }

    let lastError = null;
    for (const attempt of attempts) {
      try {
        return await attempt();
      } catch (err) {
        lastError = err;
      }
    }

    throw lastError || new Error('Không có file để xem');
  },

  async fetchMenteeDocumentPreview(menteeId, docId) {
    const token = localStorage.getItem('admin_token');
    const response = await fetch(
      `${API_BASE}/api/admin/mentees/${menteeId}/documents/${docId}/file`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Không mở được file');
    }
    const blob = await response.blob();
    return {
      url: URL.createObjectURL(blob),
      mimeType: blob.type || response.headers.get('Content-Type') || '',
    };
  },

  getFeedback: () => request('/api/admin/feedback'),

  updateFeedback: (id, body) =>
    request(`/api/admin/feedback/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteFeedback: (id) =>
    request(`/api/admin/feedback/${id}`, {
      method: 'DELETE',
    }),

  getActivities,
  getActivityAdmins,

  getAccessRequests: () => request('/api/admin/access-requests'),

  getTeamAdmins: () => request('/api/admin/access-requests/team'),

  revokeTeamAdmin: (id) =>
    request(`/api/admin/access-requests/team/${id}/revoke`, {
      method: 'POST',
    }),

  reviewAccessRequest: (id, body) =>
    request(`/api/admin/access-requests/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  bulkReviewAccessRequests: (items) =>
    request('/api/admin/access-requests/bulk-review', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  parseProfileActivity: (body) =>
    request('/api/admin/profile-activities/parse', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  createProfileActivity: (body) =>
    request('/api/admin/profile-activities', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  bulkImportParseProfileActivities: async (file) => {
    const token = localStorage.getItem('admin_token');
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/api/admin/profile-activities/bulk-import/parse`, {
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

  bulkCreateProfileActivities: (items) =>
    request('/api/admin/profile-activities/bulk-import/create', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  getProfileActivities: () => request('/api/admin/profile-activities'),

  getProfileActivityRegistrations: (activityId) =>
    request(`/api/admin/profile-activities/${activityId}/registrations`),

  deleteProfileActivity: (activityId) =>
    request(`/api/admin/profile-activities/${activityId}`, {
      method: 'DELETE',
    }),

  updateProfileActivity: (activityId, body) =>
    request(`/api/admin/profile-activities/${activityId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  inviteProfileActivityMentees: (activityId, body) =>
    request(`/api/admin/profile-activities/${activityId}/invite`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  upsertProfileActivityGroup: (activityId, body) =>
    request(`/api/admin/profile-activities/${activityId}/groups`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  suggestProfileActivityGroupName: (activityId) =>
    request(`/api/admin/profile-activities/${activityId}/groups/suggest-name`),

  addMenteeToProfileActivityGroup: (activityId, groupId, body) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}/add-mentee`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  removeMenteeFromProfileActivityGroup: (activityId, groupId, body) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}/remove-mentee`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  moveProfileActivityMenteeGroup: (activityId, menteeId, body) =>
    request(`/api/admin/profile-activities/${activityId}/registrations/${menteeId}/move-group`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  promoteProfileActivityIndividualToGroup: (activityId, menteeId) =>
    request(`/api/admin/profile-activities/${activityId}/registrations/${menteeId}/promote-to-group`, {
      method: 'POST',
    }),

  dismissProfileActivityFinalizeReminder: (activityId, groupId) =>
    request(
      `/api/admin/profile-activities/${activityId}/groups/${groupId}/dismiss-finalize-reminder`,
      { method: 'POST' },
    ),
  finalizeProfileActivityGroup: (activityId, groupId) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}/finalize`, {
      method: 'POST',
    }),

  deleteProfileActivityGroup: (activityId, groupId) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}`, {
      method: 'DELETE',
    }),

  setProfileActivityGroupLeader: (activityId, groupId, body) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}/leader`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  approveProfileActivity: (activityId) =>
    request(`/api/admin/profile-activities/${activityId}/approve`, { method: 'POST' }),

  rejectProfileActivity: (activityId) =>
    request(`/api/admin/profile-activities/${activityId}/reject`, { method: 'POST' }),

  approveProfileActivityGroup: (activityId, groupId) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}/approve`, {
      method: 'POST',
    }),

  rejectProfileActivityGroup: (activityId, groupId) =>
    request(`/api/admin/profile-activities/${activityId}/groups/${groupId}/reject`, {
      method: 'POST',
    }),

  rejectProfileActivityRegistration: (activityId, menteeId, body = {}) =>
    request(`/api/admin/profile-activities/${activityId}/registrations/${menteeId}/reject`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  approveProfileActivityRegistrationReject: (activityId, menteeId) =>
    request(
      `/api/admin/profile-activities/${activityId}/registrations/${menteeId}/reject/approve`,
      { method: 'POST' },
    ),

  denyProfileActivityRegistrationReject: (activityId, menteeId) =>
    request(
      `/api/admin/profile-activities/${activityId}/registrations/${menteeId}/reject/deny`,
      { method: 'POST' },
    ),

  updateProfileActivityKeeptrack: (activityId, menteeId, body) =>
    request(`/api/admin/profile-activities/${activityId}/registrations/${menteeId}/keeptrack`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getProfileActivityKeeptrackReviews: () =>
    request('/api/admin/profile-activities/keeptrack-reviews'),

  viewProfileActivityKeeptrackReview: (activityId, menteeId) =>
    request(
      `/api/admin/profile-activities/${activityId}/registrations/${menteeId}/keeptrack-reviews/view`,
      { method: 'POST' },
    ),

  rejectProfileActivityKeeptrackReview: (activityId, menteeId, body = {}) =>
    request(
      `/api/admin/profile-activities/${activityId}/registrations/${menteeId}/keeptrack-reviews/reject`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  bulkViewProfileActivityKeeptrackReviews: (items) =>
    request('/api/admin/profile-activities/keeptrack-reviews/view-bulk', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  getProfileActivityKeeptrackAbandonRequests: () =>
    request('/api/admin/profile-activities/keeptrack-abandon-requests'),

  approveProfileActivityKeeptrackAbandon: (activityId, menteeId) =>
    request(
      `/api/admin/profile-activities/${activityId}/registrations/${menteeId}/keeptrack-abandon/approve`,
      { method: 'POST' },
    ),

  rejectProfileActivityKeeptrackAbandon: (activityId, menteeId, body = {}) =>
    request(
      `/api/admin/profile-activities/${activityId}/registrations/${menteeId}/keeptrack-abandon/reject`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  getProfileActivityProgressTracking: () =>
    request('/api/admin/profile-activities/progress-tracking'),

  removeProfileActivityProgressTrackingRow: (activityId, body) =>
    request(`/api/admin/profile-activities/${activityId}/progress-tracking`, {
      method: 'DELETE',
      body: JSON.stringify(body),
    }),

  getMenteeRegistrations: () => request('/api/admin/mentee-registrations'),

  reviewMenteeRegistration: (id, body) =>
    request(`/api/admin/mentee-registrations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  reviewMenteeDocument: (menteeId, docId, body) =>
    request(`/api/admin/mentees/${menteeId}/documents/${docId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  uploadMenteeDocument: async (menteeId, docId, file) => {
    const token = localStorage.getItem('admin_token');
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${API_BASE}/api/admin/mentees/${menteeId}/documents/${docId}/upload`,
      {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      },
    );

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Có lỗi xảy ra (HTTP ${response.status})`);
    }
    return data;
  },

  updateMenteeApplyProgress: (menteeId, body) =>
    request(`/api/admin/mentees/${menteeId}/apply-progress`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  updateMenteeMentorInfo: (menteeId, body) =>
    request(`/api/admin/mentees/${menteeId}/mentor-info`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  reviewMenteeApplyProgress: (menteeId, body) =>
    request(`/api/admin/mentees/${menteeId}/apply-progress/review`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  modifyMenteeApplyProgressRows: (menteeId, action) =>
    request(`/api/admin/mentees/${menteeId}/apply-progress/rows`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    }),

  ackApplyProgressL2: (menteeId) =>
    request(`/api/admin/mentees/${menteeId}/apply-progress/ack-l2`, {
      method: 'POST',
    }),

  updateMenteeHdnkNckh: (menteeId, body) =>
    request(`/api/admin/mentees/${menteeId}/hdnk-nckh`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  setMenteeHdnkNckhReminder: (menteeId, body) =>
    request(`/api/admin/mentees/${menteeId}/hdnk-nckh/reminder`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  ackMenteeHdnkNckh: (menteeId) =>
    request(`/api/admin/mentees/${menteeId}/hdnk-nckh/ack`, {
      method: 'POST',
    }),

  ackMenteeL2Activity: (menteeId, body) =>
    request(`/api/admin/mentees/${menteeId}/l2-activity/ack`, {
      method: 'POST',
      body: JSON.stringify(body || {}),
    }),

  remindMissingDocuments: (menteeId, docIds) =>
    request(`/api/admin/mentees/${menteeId}/documents/remind-missing`, {
      method: 'POST',
      body: JSON.stringify({ doc_ids: docIds }),
    }),

  remindProfileInfo: (menteeId) =>
    request(`/api/admin/mentees/${menteeId}/profile/remind`, {
      method: 'POST',
    }),

  approveSelectedMenteeDocuments: (menteeId, docIds) =>
    request(`/api/admin/mentees/${menteeId}/documents/approve-selected`, {
      method: 'POST',
      body: JSON.stringify({ doc_ids: docIds }),
    }),

  approveLoginRequest: (userId, requestId) =>
    request(`/api/admin/users/${userId}/login-requests/${requestId}/approve`, {
      method: 'POST',
    }),

  downloadMenteeDocument(menteeId, docId, options = {}) {
    const params = new URLSearchParams({
      format: options.format || 'pdf',
      variant: options.variant || 'original',
    });
    return downloadBinary(
      `${API_BASE}/api/admin/mentees/${menteeId}/documents/${docId}/download?${params}`,
      `document-${docId}`,
    );
  },

  downloadSupportingMaterials(menteeId, options = {}) {
    const params = new URLSearchParams({
      format: options.format || 'pdf',
      variant: options.variant || 'original',
    });
    return downloadBinary(
      `${API_BASE}/api/admin/mentees/${menteeId}/documents/supporting-materials/download?${params}`,
      'supporting-materials.zip',
    );
  },

  downloadSelectedMenteeDocuments(menteeId, docIds, options = {}) {
    const token = localStorage.getItem('admin_token');
    return fetch(`${API_BASE}/api/admin/mentees/${menteeId}/documents/download-selected`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        doc_ids: docIds,
        format: options.format || 'pdf',
        variant: options.variant || 'original',
      }),
    }).then(async (response) => {
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Không tải được file');
      }
      const blob = await response.blob();
      const filename = parseDownloadFilename(response, 'documents.zip');
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
      return filename;
    });
  },

};
