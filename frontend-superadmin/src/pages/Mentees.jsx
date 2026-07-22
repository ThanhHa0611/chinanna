import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { matchesNameSearch } from '../utils/searchByName';
import { formatLevel1MentorLine } from '../utils/mentorDisplay';

export default function Mentees({ onCountChange }) {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    api
      .getMentees()
      .then((data) => {
        const nextGroups = data.groups || [];
        setGroups(nextGroups);
        onCountChange?.(data.total_count ?? nextGroups.reduce(
          (sum, group) => sum + (group.mentees?.length || 0),
          0,
        ));
        if (nextGroups.length) {
          setExpandedGroup(nextGroups[0].mentor);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [onCountChange]);

  const filteredGroups = useMemo(() => {
    const normalized = (searchQuery || '').trim();
    if (!normalized) return groups;
    return groups
      .map((group) => ({
        ...group,
        mentees: (group.mentees || []).filter((mentee) =>
          matchesNameSearch(mentee, searchQuery, [
            'full_name',
            'username',
            'email',
            'zalo_phone',
            'apply_direction',
          ]),
        ),
      }))
      .filter((group) => group.mentees.length > 0);
  }, [groups, searchQuery]);

  const totalMentees = groups.reduce(
    (sum, group) => sum + (group.mentees?.length || 0),
    0,
  );
  const visibleMentees = filteredGroups.reduce(
    (sum, group) => sum + (group.mentees?.length || 0),
    0,
  );

  return (
    <>
      <div className="page-head">
        <div className="page-head-row">
          <h2>Mentee toàn hệ thống</h2>
          {!loading && (
            <span className="page-head-badge">
              {totalMentees} mentee
            </span>
          )}
        </div>
        <p>
          Theo dõi mentee của Mentor Thanh Hà. Bấm mentee để xem đầy đủ hồ sơ.
        </p>
      </div>

      {error && <p className="form-error panel-error">{error}</p>}

      {!loading && totalMentees > 0 && (
        <div className="page-search">
          <label className="page-search-label" htmlFor="mentee-search">
            Tìm kiếm ({visibleMentees}/{totalMentees})
            <input
              id="mentee-search"
              type="search"
              className="page-search-input"
              placeholder="Theo tên, email, Zalo hoặc phương hướng..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </label>
        </div>
      )}

      {loading ? (
        <p className="loader">Đang tải...</p>
      ) : groups.length === 0 ? (
        <div className="panel-card">
          <p className="muted">Chưa có mentee nào.</p>
        </div>
      ) : filteredGroups.length === 0 ? (
        <div className="panel-card">
          <p className="muted">Không tìm thấy mentee phù hợp.</p>
        </div>
      ) : (
        <div className="team-sections">
          {filteredGroups.map((group) => {
            const isOpen = expandedGroup === group.mentor;
            return (
              <section key={group.mentor} className="panel-card team-section">
                <button
                  type="button"
                  className="team-toggle"
                  onClick={() =>
                    setExpandedGroup(isOpen ? null : group.mentor)
                  }
                  aria-expanded={isOpen}
                >
                  <h3 className="team-title">
                    {group.mentor_label || formatLevel1MentorLine(group.mentor) || group.mentor}
                  </h3>
                  <span className="team-count">{group.mentees.length} mentee</span>
                </button>

                {isOpen && (
                  <div className="mentee-list">
                    {group.mentees.map((mentee) => (
                      <Link
                        key={mentee.id}
                        to={`/mentees/${mentee.id}`}
                        className="mentee-row"
                      >
                        <span className="mentee-row-name">
                          {mentee.full_name || mentee.username}
                          {mentee.unread_documents_count > 0 && (
                            <span className="notify-dot notify-dot-soft" title="Có giấy tờ mới" />
                          )}
                          {mentee.unread_feedback_count > 0 && (
                            <span className="notify-dot" title="Có phản hồi mới" />
                          )}
                        </span>
                        <span
                          className={`muted mentee-row-subline${
                            (mentee.mentor_apply_direction_label || mentee.mentor_apply_direction || '')
                              .trim()
                              ? ' mentee-row-direction'
                              : ''
                          }`}
                        >
                          {mentee.mentor_apply_direction_label ||
                            mentee.mentor_apply_direction?.trim() ||
                            'Chưa điền phương hướng'}
                        </span>
                        <span className="mentee-row-meta">
                          {mentee.scholarship_system_label || '—'}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
