import { feedLineLink, feedLineText } from '../utils/profileActivities';

export default function ActivityInlineLink({ activity, fallback = '—', className = '' }) {
  const text = activity ? feedLineText(activity) : fallback;
  const link = activity ? feedLineLink(activity) : '';

  return (
    <span className={className || undefined}>
      {text || fallback}
      {link ? (
        <>
          {' '}
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="profile-activity-inline-link"
          >
            (Link)
          </a>
        </>
      ) : null}
    </span>
  );
}
