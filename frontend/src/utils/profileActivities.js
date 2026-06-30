export function format_activity_feed_line(activity, mentee) {
  const pieces = [];
  const name = (activity?.activity_name || '').trim() || 'Hoạt động hồ sơ';
  pieces.push(name);
  if (activity?.organizer) {
    pieces.push(`của ${activity.organizer}`);
  }
  if (activity?.content) {
    pieces.push(`về ${activity.content}`);
  }
  if (activity?.target_audience) {
    pieces.push(`dành cho ${activity.target_audience}`);
  }
  if (activity?.deadline) {
    pieces.push(`deadline ${activity.deadline}`);
  }
  return pieces.join(', ');
}
