const LOGO_SRC = '/tron-tru-badge.png';

export default function BrandMark({ lines = [], subtitle }) {
  return (
    <div className="brand-mark">
      <img src={LOGO_SRC} alt="" className="brand-mark-logo" aria-hidden="true" />
      <div className="brand-mark-text">
        {lines.length > 0 ? (
          lines.map((line) => (
            <span key={line.text} className={`brand-mark-line brand-mark-${line.variant}`}>
              {line.text}
            </span>
          ))
        ) : (
          <>
            <span className="brand-mark-line brand-mark-title">Du học Trung Quốc</span>
            {subtitle ? <span className="brand-mark-line brand-mark-subtitle">{subtitle}</span> : null}
          </>
        )}
      </div>
    </div>
  );
}
