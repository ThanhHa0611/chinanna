import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, documentFileUrl } from '../services/api';
import { formatDateTime } from '../utils/formatDateTime';
import { formatLevel1MentorLine } from '../utils/mentorDisplay';
import {
  applyDegreeLevelLabel,
  mentorApplyDirectionCombinedLabel,
  term3LanguageSemesterLabel,
} from '../data/applyDegree';

const MENTOR_STATUS_LABELS = {
  'chờ phản hồi': 'Chờ phản hồi',
  'đã duyệt': 'Đã duyệt',
  'cần chỉnh sửa': 'Cần chỉnh sửa',
};

const ENGLISH_SKILLS = [
  { key: 'overall', label: 'Overall' },
  { key: 'listening', label: 'Nghe' },
  { key: 'speaking', label: 'Nói' },
  { key: 'reading', label: 'Đọc' },
  { key: 'writing', label: 'Viết' },
];

const CHINESE_SKILLS = [
  { key: 'overall', label: 'Overall' },
  { key: 'listening', label: 'Nghe' },
  { key: 'reading', label: 'Đọc' },
  { key: 'writing', label: 'Viết' },
  { key: 'hskk', label: 'HSKK' },
];

async function openDocumentFile(menteeId, docId) {
  const token = localStorage.getItem('superadmin_token');
  const response = await fetch(documentFileUrl(menteeId, docId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Không mở được file');
  }
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
}

function LanguageScores({ languageDoc }) {
  if (!languageDoc) {
    return <p className="muted">Chưa có điểm chứng chỉ ngoại ngữ.</p>;
  }

  const languages = languageDoc.languages || [];
  const english = languageDoc.english || {};
  const chinese = languageDoc.chinese || {};

  return (
    <div className="language-block">
      {languageDoc.certificate_name && (
        <p>
          <span className="info-label">Tên chứng chỉ</span>
          <strong>{languageDoc.certificate_name}</strong>
        </p>
      )}
      {languages.includes('english') && (
        <div className="language-group">
          <strong>Tiếng Anh</strong>
          <div className="score-grid">
            {ENGLISH_SKILLS.filter((s) => english[s.key]).map((skill) => (
              <div key={skill.key}>
                <span className="info-label">{skill.label}</span>
                <strong>{english[skill.key]}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
      {languages.includes('chinese') && (
        <div className="language-group">
          <strong>Tiếng Trung</strong>
          <div className="score-grid">
            {CHINESE_SKILLS.filter((s) => chinese[s.key]).map((skill) => (
              <div key={skill.key}>
                <span className="info-label">{skill.label}</span>
                <strong>{chinese[skill.key]}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MenteeDetail() {
  const { menteeId } = useParams();
  const [mentee, setMentee] = useState(null);
  const [feedback, setFeedback] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fileError, setFileError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    Promise.all([api.getMentee(menteeId), api.getMenteeFeedback(menteeId)])
      .then(([detail, feedbackData]) => {
        if (cancelled) return;
        setMentee(detail);
        setFeedback(feedbackData.items || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [menteeId]);

  const languageDoc = mentee?.documents?.find((doc) => doc.doc_id === 'language');

  const handleViewFile = async (docId) => {
    setFileError('');
    try {
      await openDocumentFile(menteeId, docId);
    } catch (err) {
      setFileError(err.message);
    }
  };

  if (loading) {
    return <p className="loader">Đang tải hồ sơ mentee...</p>;
  }

  if (error || !mentee) {
    return (
      <>
        <Link to="/mentees" className="btn btn-outline btn-sm back-btn">
          ← Quay lại danh sách mentee
        </Link>
        <p className="form-error panel-error">{error || 'Không tìm thấy mentee'}</p>
      </>
    );
  }

  return (
    <>
      <Link to="/mentees" className="btn btn-outline btn-sm back-btn">
        ← Quay lại danh sách mentee
      </Link>

      <div className="page-head">
        <h2>{mentee.full_name || mentee.username}</h2>
        {(mentee.mentor_apply_direction_label || mentee.mentor_apply_direction || '').trim() && (
          <p className="mentee-apply-direction-under-name">
            {mentee.mentor_apply_direction_label || mentee.mentor_apply_direction}
          </p>
        )}
        <p>
          {formatLevel1MentorLine(mentee.mentor) || mentee.mentor || '—'}
          {mentee.email ? ` · ${mentee.email}` : ''}
        </p>
      </div>

      {fileError && <p className="form-error panel-error">{fileError}</p>}

      <div className="panel-card">
        <h3>Thông tin mentee</h3>
        <div className="info-grid">
          <div>
            <span className="info-label">Họ tên</span>
            <strong>{mentee.full_name || '—'}</strong>
            {(mentorApplyDirectionCombinedLabel(mentee) ||
              mentee.mentor_apply_direction_label ||
              mentee.mentor_apply_direction ||
              '').trim() && (
              <p className="mentee-apply-direction-under-name">
                {mentorApplyDirectionCombinedLabel(mentee) ||
                  mentee.mentor_apply_direction_label ||
                  mentee.mentor_apply_direction}
              </p>
            )}
          </div>
          <div>
            <span className="info-label">Hướng apply</span>
            <strong>
              {mentorApplyDirectionCombinedLabel(mentee) ||
                mentee.mentor_apply_direction_label ||
                mentee.mentor_apply_direction?.trim() ||
                '—'}
            </strong>
          </div>
          <div>
            <span className="info-label">Email</span>
            <strong>{mentee.email || '—'}</strong>
          </div>
          <div>
            <span className="info-label">Số Zalo</span>
            <strong>{mentee.zalo_phone || '—'}</strong>
          </div>
          <div>
            <span className="info-label">Mentor</span>
            <strong>{formatLevel1MentorLine(mentee.mentor) || mentee.mentor || '—'}</strong>
          </div>
          <div>
            <span className="info-label">App học bổng</span>
            <strong>{mentee.scholarship_system_label || '—'}</strong>
          </div>
          <div>
            <span className="info-label">Hệ apply</span>
            <strong>
              {mentee.apply_degree_level_label ||
                applyDegreeLevelLabel(mentee.apply_degree_level)}
            </strong>
          </div>
          {mentee.mentor === 'Thanh Hà' && (
            <div>
              <span className="info-label">Kì 3/2027 — 1 kì tiếng?</span>
              <strong>
                {mentee.term3_2027_language_semester_label ||
                  term3LanguageSemesterLabel(mentee.term3_2027_language_semester)}
              </strong>
            </div>
          )}
          <div>
            <span className="info-label">Email phụ huynh</span>
            <strong>{mentee.parent_email || '—'}</strong>
          </div>
          <div>
            <span className="info-label">Email clone</span>
            <strong>{mentee.apply_clone_email || '—'}</strong>
          </div>
          <div>
            <span className="info-label">Pass clone</span>
            <strong>{mentee.apply_clone_password || '—'}</strong>
          </div>
          <div>
            <span className="info-label">Ngày tạo</span>
            <strong>{formatDateTime(mentee.created_at)}</strong>
          </div>
        </div>
        <div className="subsection">
          <h4>Chứng chỉ ngoại ngữ</h4>
          <LanguageScores languageDoc={languageDoc} />
        </div>
      </div>

      <div className="panel-card">
        <h3>Tiến độ apply</h3>
        <div className="apply-progress-table-wrap">
          <table className="apply-progress-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Tên trường</th>
                <th>Ngành apply</th>
                <th>Link</th>
                <th>Loại hb</th>
                <th>Trợ cấp</th>
                <th>Phí báo danh</th>
                <th>Tiến độ</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {(mentee.apply_progress?.rows || []).map((row) => (
                <tr key={row.row_num}>
                  <td>{row.row_num}</td>
                  <td>{row.school_name || '—'}</td>
                  <td>{row.apply_major || '—'}</td>
                  <td>{row.link || '—'}</td>
                  <td>{row.scholarship_type || '—'}</td>
                  <td>{row.allowance || '—'}</td>
                  <td>{row.registration_fee || '—'}</td>
                  <td>{row.progress || '—'}</td>
                  <td>{row.note || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel-card">
        <h3>
          Tài liệu Apply ({mentee.uploaded_count}/{mentee.total_documents_count})
        </h3>
        <div className="apply-preferred-schools-note">
          <strong>Trường ưa thích (mentee ghi chú)</strong>
          <p className={mentee.preferred_schools_note?.trim() ? '' : 'muted'}>
            {mentee.preferred_schools_note?.trim() || 'Mentee chưa ghi chú trường ưa thích.'}
          </p>
        </div>
        <div className="doc-table-wrap">
          <table className="doc-table">
            <thead>
              <tr>
                <th>Giấy tờ</th>
                <th>Trạng thái</th>
                <th>Mentor</th>
                <th>Nhận xét</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(mentee.documents || []).map((doc) => (
                <tr key={doc.doc_id} className={doc.uploaded ? '' : 'doc-missing'}>
                  <td>{doc.label}</td>
                  <td>{doc.uploaded ? 'Đã nộp' : 'Chưa nộp'}</td>
                  <td>
                    {doc.mentor_status
                      ? MENTOR_STATUS_LABELS[doc.mentor_status] || doc.mentor_status
                      : '—'}
                  </td>
                  <td>{doc.mentor_comment || '—'}</td>
                  <td>
                    {doc.has_file && !doc.is_bundle && (
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() => handleViewFile(doc.doc_id)}
                      >
                        Xem
                      </button>
                    )}
                    {doc.is_bundle && doc.has_file && (
                      <span className="muted">Gói tải (mentor)</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel-card">
        <h3>Phản hồi ({feedback.length})</h3>
        {feedback.length === 0 ? (
          <p className="muted">Mentee chưa gửi phản hồi nào.</p>
        ) : (
          <div className="feedback-list">
            {feedback.map((item, index) => (
              <article key={item.id} className="feedback-item">
                <div className="feedback-item-head">
                  <strong>Tin #{feedback.length - index}</strong>
                  <span className="badge">{item.status}</span>
                  <time>{formatDateTime(item.created_at)}</time>
                </div>
                <div className="feedback-thread">
                  {(item.messages || [{ content: item.content, sender: 'mentee' }]).map(
                    (message, msgIndex) => (
                      <div
                        key={message.id || msgIndex}
                        className={`feedback-message feedback-message-${message.sender || 'mentee'}`}
                      >
                        <span className="feedback-sender">
                          {message.sender === 'mentor' ? 'Mentor' : 'Mentee'}
                        </span>
                        <p>{message.content}</p>
                        {message.created_at && (
                          <time className="muted">{formatDateTime(message.created_at)}</time>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
