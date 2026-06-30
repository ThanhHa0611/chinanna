import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { matchesNameSearch } from '../utils/searchByName';
import { formatDateTime } from '../utils/formatDateTime';
import { formatLevel1MentorLine } from '../utils/mentorDisplay';

export default function AccessRequests() {
  const { admin } = useAuth();
  const isSuperAdmin = Boolean(admin?.is_super_admin);
  const [tab, setTab] = useState('pending');
  const [team, setTeam] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [processingId, setProcessingId] = useState(null);
  const [revokeTarget, setRevokeTarget] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const accessSearchFields = [
    'full_name',
    'username',
    'email',
    'zalo_phone',
    'mentee_name',
    'old_ip',
    'new_ip',
    'warning_message',
  ];

  const filteredRequests = useMemo(
    () => requests.filter((item) => matchesNameSearch(item, searchQuery, accessSearchFields)),
    [requests, searchQuery],
  );

  const filteredTeam = useMemo(
    () => team.filter((item) => matchesNameSearch(item, searchQuery, accessSearchFields)),
    [team, searchQuery],
  );

  const loadData = () => {
    setLoading(true);
    setError('');
    const loaders = [api.getAccessRequests()];
    if (isSuperAdmin) {
      loaders.push(api.getTeamAdmins());
    }
    Promise.all(loaders)
      .then((results) => {
        setRequests(results[0] || []);
        setTeam(isSuperAdmin ? results[1] || [] : []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [isSuperAdmin]);

  const handleReview = async (item, status) => {
    setProcessingId(`${item.request_type}-${item.id}`);
    setMessage('');
    setError('');
    try {
      const body = {
        status,
        request_type: item.request_type,
      };
      if (item.request_type === 'mentee_login_ip') {
        body.user_id = item.user_id;
      }
      const result = await api.reviewAccessRequest(item.id, body);
      setMessage(result.message);
      loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingId(null);
    }
  };

  const formatIpLocation = (ip, location) => {
    if (!ip && !location) return '—';
    if (ip && location) return `${ip} · ${location}`;
    return ip || location || '—';
  };

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    setProcessingId(revokeTarget.id);
    setMessage('');
    setError('');
    try {
      const result = await api.revokeTeamAdmin(revokeTarget.id);
      setMessage(result.message);
      setRevokeTarget(null);
      loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingId(null);
    }
  };

  const branchLabel = admin?.mentor_name
    ? formatLevel1MentorLine(admin.mentor_name)
    : 'toàn hệ thống';

  const tabs = isSuperAdmin
    ? [
        { id: 'team', label: 'Team mentor' },
        { id: 'pending', label: 'Chờ duyệt' },
      ]
    : [{ id: 'pending', label: 'Chờ duyệt' }];

  return (
    <>
      <div className="page-head">
        <h2>Cấp quyền</h2>
        <p>
          Duyệt đăng ký mentee, mentor và đăng nhập IP mới — {branchLabel}
        </p>
      </div>

      <div className="page-tabs">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`page-tab${tab === item.id ? ' active' : ''}${item.id === 'pending' && filteredRequests.length > 0 ? ' page-tab-alert' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
            {item.id === 'pending' && filteredRequests.length > 0 ? ` (${filteredRequests.length})` : ''}
          </button>
        ))}
      </div>

      {requests.length > 0 && tab === 'pending' && (
        <div className="panel-card alert-card access-requests-alert">
          <p>
            Có <strong>{requests.length}</strong> yêu cầu cấp quyền cần xử lí.
          </p>
        </div>
      )}

      {message && <p className="form-success panel-error">{message}</p>}
      {error && <p className="form-error panel-error">{error}</p>}

      {!loading && (requests.length > 0 || team.length > 0) && (
        <div className="page-search">
          <label className="page-search-label" htmlFor="access-search">
            Tìm kiếm
            <input
              id="access-search"
              type="search"
              className="page-search-input"
              placeholder="Theo tên..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </label>
        </div>
      )}

      {loading ? (
        <p className="loader">Đang tải...</p>
      ) : tab === 'team' && isSuperAdmin ? (
        <div className="panel-card">
          {filteredTeam.length === 0 ? (
            <p className="muted">
              {team.length === 0 ? 'Chưa có admin nào trong team.' : 'Không tìm thấy kết quả phù hợp.'}
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Họ tên</th>
                    <th>Email</th>
                    <th>Tên đăng nhập</th>
                    <th>Duyệt lúc</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTeam.map((member) => (
                    <tr key={member.id}>
                      <td>{member.full_name || member.username}</td>
                      <td>{member.email}</td>
                      <td>{member.username}</td>
                      <td>{formatDateTime(member.reviewed_at)}</td>
                      <td className="action-cell">
                        <button
                          type="button"
                          className="btn btn-outline btn-sm btn-danger-text"
                          disabled={processingId === member.id}
                          onClick={() => setRevokeTarget(member)}
                        >
                          Xóa quyền admin
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="panel-card">
          {filteredRequests.length === 0 ? (
            <p className="muted">
              {requests.length === 0 ? 'Không có yêu cầu đang chờ.' : 'Không tìm thấy kết quả phù hợp.'}
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Loại</th>
                    <th>Cảnh báo</th>
                    <th>Họ tên mentee</th>
                    <th>IP & vị trí cũ</th>
                    <th>IP & vị trí mới</th>
                    <th>Email / Zalo</th>
                    <th>Team</th>
                    <th>Yêu cầu lúc</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRequests.map((req) => {
                    const rowKey = `${req.request_type}-${req.id}`;
                    const isLoginIp = req.request_type === 'mentee_login_ip';
                    const isMenteeReg = req.request_type === 'mentee';
                    const roleClass = isLoginIp
                      ? 'role-badge-login'
                      : isMenteeReg
                        ? 'role-badge-mentee'
                        : 'role-badge-mentor';
                    return (
                      <tr key={rowKey} className={isLoginIp ? 'access-row-login-ip' : ''}>
                        <td>
                          <span className={`role-badge ${roleClass}`}>{req.role_label}</span>
                        </td>
                        <td>
                          {isLoginIp ? (
                            <div className="access-login-warning">
                              <strong>{req.warning_message || 'Đăng nhập từ IP mới'}</strong>
                              {req.device_label && (
                                <span className="muted">{req.device_label}</span>
                              )}
                            </div>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                        <td>
                          {isLoginIp
                            ? req.mentee_name || req.full_name || '—'
                            : isMenteeReg
                              ? req.full_name || '—'
                              : req.full_name || req.username || '—'}
                        </td>
                        <td>
                          {isLoginIp
                            ? formatIpLocation(req.old_ip, req.old_location_label)
                            : isMenteeReg
                              ? req.registration_location_label || '—'
                              : '—'}
                        </td>
                        <td>
                          {isLoginIp
                            ? formatIpLocation(req.new_ip, req.new_location_label)
                            : '—'}
                        </td>
                        <td>
                          <div>{req.email || '—'}</div>
                          {isMenteeReg && req.zalo_phone && (
                            <span className="muted">Zalo: {req.zalo_phone}</span>
                          )}
                          {isLoginIp && req.zalo_phone && (
                            <span className="muted">Zalo: {req.zalo_phone}</span>
                          )}
                        </td>
                        <td>{formatLevel1MentorLine(req.team) || req.team || '—'}</td>
                        <td>{formatDateTime(req.requested_at)}</td>
                        <td className="action-cell">
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={processingId === rowKey}
                            onClick={() => handleReview(req, 'approved')}
                          >
                            Duyệt
                          </button>
                          <button
                            type="button"
                            className="btn btn-outline btn-sm"
                            disabled={processingId === rowKey}
                            onClick={() => handleReview(req, 'rejected')}
                          >
                            Từ chối
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {revokeTarget && (
        <div className="modal-backdrop" onClick={() => setRevokeTarget(null)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <h3>Thu hồi quyền admin</h3>
            <p>
              Bạn có chắc muốn xóa quyền admin của{' '}
              <strong>{revokeTarget.full_name || revokeTarget.username}</strong>{' '}
              ({revokeTarget.email})?
            </p>
            <p className="muted modal-note">
              Sau khi xác nhận, tài khoản này không thể đăng nhập hệ thống admin nữa.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setRevokeTarget(null)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={processingId === revokeTarget.id}
                onClick={handleRevoke}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
