import { useEffect, useState } from 'react';
import {
  APPLY_DEGREE_SELECT_OPTIONS,
  APPLY_LANGUAGE_OPTIONS,
  MENTOR_APPLY_DIRECTION_OPTIONS,
  researchDirectionDisplayText,
  TERM3_LANGUAGE_SHORT_OPTIONS,
  normalizeMentorApplyDirectionValue,
} from '../data/applyDegree';

function ResearchDirectionInput({
  mentee,
  menteeId,
  savingField,
  onFieldChange,
  selectClassName,
  disabled,
}) {
  const id = menteeId || mentee.id;
  const [draft, setDraft] = useState('');

  useEffect(() => {
    setDraft(researchDirectionDisplayText(mentee));
  }, [mentee?.id, mentee?.research_direction, mentee?.research_direction_label]);

  const isSaving = savingField === `${id}:research_direction`;

  return (
    <label className="mentee-classification-field">
      <span className="info-label">Phương hướng NC (mentor điền)</span>
      <input
        type="text"
        className={selectClassName}
        value={draft}
        placeholder="VD: Hướng NC, NC kinh tế..."
        disabled={disabled || isSaving}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          const trimmed = draft.trim();
          const current = researchDirectionDisplayText(mentee);
          if (trimmed !== current) {
            onFieldChange(id, 'research_direction', trimmed);
          }
        }}
      />
    </label>
  );
}

export default function MenteeClassificationFields({
  mentee,
  menteeId,
  savingField = '',
  onFieldChange,
  showDirection = false,
  showTerm = false,
  showDegree = true,
  showResearchDirection = false,
  showLanguage = false,
  selectClassName = 'mentee-class-select',
  disabled = false,
}) {
  if (!mentee) return null;

  const id = menteeId || mentee.id;

  const isSaving = (field) => savingField === `${id}:${field}`;

  const wishFields = [
    { field: 'mentor_apply_direction', label: 'Nguyện vọng 1' },
    { field: 'mentor_apply_direction_2', label: 'Nguyện vọng 2 (nếu có)' },
    { field: 'mentor_apply_direction_3', label: 'Nguyện vọng 3 (nếu có)' },
  ];
  const wishValues = wishFields.map(({ field }) =>
    normalizeMentorApplyDirectionValue(mentee[field]),
  );

  return (
    <div className="mentee-classification-grid">
      {showDirection && (
        <div className="mentee-classification-field mentee-classification-wishes">
          <span className="info-label">Hướng apply (khối ngành)</span>
          {wishFields.map(({ field, label }, index) => {
            const currentValue = wishValues[index];
            const takenByOthers = wishValues.filter((_, i) => i !== index);
            const previousEmpty = index > 0 && !wishValues[index - 1];
            return (
              <label key={field} className="mentee-classification-wish">
                <span className="mentee-classification-wish-label">{label}</span>
                <select
                  className={selectClassName}
                  value={currentValue}
                  disabled={disabled || isSaving(field) || previousEmpty}
                  onChange={(e) => onFieldChange(id, field, e.target.value)}
                >
                  {MENTOR_APPLY_DIRECTION_OPTIONS.filter(
                    (option) =>
                      !option.value ||
                      option.value === currentValue ||
                      !takenByOthers.includes(option.value),
                  ).map((option) => (
                    <option key={option.value || 'empty'} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
      )}
      {showResearchDirection && (
        <ResearchDirectionInput
          mentee={mentee}
          menteeId={id}
          savingField={savingField}
          onFieldChange={onFieldChange}
          selectClassName={selectClassName}
          disabled={disabled}
        />
      )}
      {showDegree && (
        <label className="mentee-classification-field">
          <span className="info-label">Hệ apply</span>
          <select
            className={selectClassName}
            value={mentee.apply_degree_level || ''}
            disabled={disabled || isSaving('apply_degree_level')}
            onChange={(e) => onFieldChange(id, 'apply_degree_level', e.target.value)}
          >
            {APPLY_DEGREE_SELECT_OPTIONS.map((option) => (
              <option key={option.value || 'empty'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {showLanguage && (
        <label className="mentee-classification-field">
          <span className="info-label">Hệ tiếng</span>
          <select
            className={selectClassName}
            value={mentee.scholarship_system || ''}
            disabled={disabled || isSaving('scholarship_system')}
            onChange={(e) => onFieldChange(id, 'scholarship_system', e.target.value)}
          >
            {APPLY_LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value || 'empty'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {showTerm && (
        <label className="mentee-classification-field">
          <span className="info-label">Kì tiếng 3/2027 (1 kì tiếng)</span>
          <select
            className={selectClassName}
            value={mentee.term3_2027_language_semester || ''}
            disabled={disabled || isSaving('term3_2027_language_semester')}
            onChange={(e) => onFieldChange(id, 'term3_2027_language_semester', e.target.value)}
          >
            {TERM3_LANGUAGE_SHORT_OPTIONS.map((option) => (
              <option key={option.value || 'empty'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
