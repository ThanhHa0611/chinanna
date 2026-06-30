import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { matchesNameSearch } from '../utils/searchByName';
import { formatDateTime } from '../utils/formatDateTime';
import { formatLevel1MentorLine } from '../utils/mentorDisplay';

const REGISTRATION_TYPES = new Set(['mentee', 'mentor']);

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

  const registrationRequests = useMemo(
    () => requests.filter((item) => REGISTRATION_TYPES.has(item.request_type)),
    [requests],
  );

  const warningRequests = useMemo(
    () => requests.filter((item) => item.request_type === 'mentee_login_ip'),
    [requests],
  );

  const registrationSearchFields = [
    'full_name',
    'username',
    'email',
    'zalo_phone',
  ];

  const warningSearchFields = [
    'mentee_name',
    'full_name',
    'old_ip',
    'new_ip',
    'old_device_label',
    'new_device_label',
  ];

  const filteredRegistration = useMemo(
    () =>
      registrationRequests.filter((item) =>
        matchesNameSearch(item, searchQuery, registrationSearchFields),
      ),
    [registrationRequests, searchQuery],
  );

  const filteredWarnings = useMemo(
    () =>
      warningRequests.filter((item) =>
        matchesNameSearch(item, searchQuery, warningSearchFields),
      ),
    [warningRequests, searchQuery],
  );

  const filteredTeam = useMemo(
    () =>
      team.filter((item) =>
        matchesNameSearch(item, searchQuery, ['full_name', 'username', 'email']),
      ),
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
        { id: 'pending', label: 'Chờ duyệt', count: filteredRegistration.length },
        { id: 'warnings', label: 'Cảnh báo', count: filteredWarnings.length },
      ]
    : [
        { id: 'pending', label: 'Chờ duyệt', count: filteredRegistration.length },
        { id: 'warnings', label: 'Cảnh báo', count: filteredWarnings.length },
      ];

  const showSearch =
    !loading &&
    (registrationRequests.length > 0 ||
      warningRequests.length > 0 ||
      team.length > 0);

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
            className={`page-tab${tab === item.id ? ' active' : ''}${item.count > 0 ? ' page-tab-alert' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
            {item.count > 0 ? ` (${item.count})` : ''}
          </button>
        ))}
      </div>

      {registrationRequests.length > 0 && tab === 'pending' && (
        <div className="panel-card alert-card access-requests-alert">
          <p>
            Có <strong>{registrationRequests.length}</strong> yêu cầu đăng ký cần duyệt.
          </p>
        </div>
      )}

      {warningRequests.length > 0 && tab === 'warnings' && (
        <div className="panel-card alert-card access-requests-alert access-warnings-alert">
          <p>
            Có <strong>{warningRequests.length}</strong> cảnh báo đăng nhập IP/thiết bị mới.
          </p>
        </div>
      )}

      {message && <p className="form-success panel-error">{message}</p>}
      {error && <p className="form-error panel-error">{error}</p>}

      {showSearch && (
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
      ) : tab === 'warnings' ? (
        <div className="panel-card">
          {filteredWarnings.length === 0 ? (
            <p className="muted">
              {warningRequests.length === 0
                ? 'Không có cảnh báo đăng nhập.'
                : 'Không tìm thấy kết quả phù hợp.'}
            </p>
          ) : (
            <div className="table-wrap">
              <table className="access-warnings-table">
                <thead>
                  <tr>
                    <th>Tên</th>
                    <th>Thiết bị cũ</th>
                    <th>Thiết bị mới</th>
                    <th>IP cũ</th>
                    <th>IP mới</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredWarnings.map((req) => {
                    const rowKey = `${req.request_type}-${req.id}`;
                    return (
                      <tr key={rowKey}>
                        <td>{req.mentee_name || req.full_name || '—'}</td>
                        <td>{req.old_device_label || '—'}</td>
                        <td>{req.new_device_label || '—'}</td>
                        <td>{req.old_ip || '—'}</td>
                        <td>{req.new_ip || '—'}</td>
                        <td className="action-cell">
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={processingId === rowKey}
                            onClick={() => handleReview(req, 'approved')}
                          >
                            Đồng ý
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
      ) : (
        <div className="panel-card">
          {filteredRegistration.length === 0 ? (
            <p className="muted">
              {registrationRequests.length === 0
                ? 'Không có yêu cầu đăng ký đang chờ.'
                : 'Không tìm thấy kết quả phù hợp.'}
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Loại</th>
                    <th>Họ tên</th>
                    <th>Email / Zalo</th>
                    <th>Team</th>
                    <th>Vị trí đăng ký</th>
                    <th>Yêu cầu lúc</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRegistration.map((req) => {
                    const rowKey = `${req.request_type}-${req.id}`;
                    const isMenteeReg = req.request_type === 'mentee';
                    const roleClass = isMenteeReg ? 'role-badge-mentee' : 'role-badge-mentor';
                    return (
                      <tr key={rowKey}>
                        <td>
                          <span className={`role-badge ${roleClass}`}>{req.role_label}</span>
                        </td>
                        <td>
                          {isMenteeReg
                            ? req.full_name || '—'
                            : req.full_name || req.username || '—'}
                        </td>
                        <td>
                          <div>{req.email || '—'}</div>
                          {isMenteeReg && req.zalo_phone && (
                            <span className="muted">Zalo: {req.zalo_phone}</span>
                          )}
                        </td>
                        <td>{formatLevel1MentorLine(req.team) || req.team || '—'}</td>
                        <td>
                          {isMenteeReg ? req.registration_location_label || '—' : '—'}
                        </td>
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
