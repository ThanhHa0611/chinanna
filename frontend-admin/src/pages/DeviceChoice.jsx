export default function DeviceChoice({ title, subtitle, onChoose }) {
  return (
    <div className="device-choice-page">
      <div className="device-choice-shell">
        <p className="device-choice-kicker">Du học Trung Quốc</p>
        <h1>{title}</h1>
        <p className="device-choice-subtitle">{subtitle}</p>
        <div className="device-choice-options">
          <button
            type="button"
            className="device-choice-card device-choice-phone"
            onClick={() => onChoose('phone')}
          >
            <span className="device-choice-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="7" y="2.5" width="10" height="19" rx="2.2" />
                <line x1="11" y1="18.5" x2="13" y2="18.5" strokeLinecap="round" />
              </svg>
            </span>
            <strong>Điện thoại</strong>
            <span className="device-choice-hint">Giao diện tối ưu iPhone, dễ thao tác một tay</span>
          </button>
          <button
            type="button"
            className="device-choice-card device-choice-laptop"
            onClick={() => onChoose('laptop')}
          >
            <span className="device-choice-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="3.5" y="5" width="17" height="11" rx="1.5" />
                <path d="M2 18.5h20" strokeLinecap="round" />
              </svg>
            </span>
            <strong>Laptop</strong>
            <span className="device-choice-hint">Giao diện đầy đủ như trên máy tính</span>
          </button>
        </div>
        <p className="device-choice-note muted">Có thể đổi lại sau trong mục Tài khoản</p>
      </div>
    </div>
  );
}
