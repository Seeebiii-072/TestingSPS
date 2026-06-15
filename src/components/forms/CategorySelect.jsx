import { CATEGORIES } from '../../config/constants.js';

export const requestCategories = CATEGORIES;

export default function CategorySelect({ id = 'request-category', onChange, value }) {
  return (
    <label className="request-field" htmlFor={id}>
      <span>Category</span>
      <select id={id} name="category" required value={value} onChange={onChange}>
        <option value="">Select the best category</option>
        {requestCategories.map((category) => (
          <option key={category.value} value={category.value}>
            {category.label}
          </option>
        ))}
      </select>
      <small>Used to route the request to the right support team.</small>
    </label>
  );
}
