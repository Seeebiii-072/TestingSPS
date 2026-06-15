import Button from '../common/Button';
import SearchInput from '../common/SearchInput';

const options = {
  source: [
    ['email', 'Email'],
    ['portal_form', 'Portal form'],
    ['chat', 'Chat'],
  ],
  status: [
    ['open', 'Open'],
    ['in_progress', 'In Progress'],
    ['waiting_approval', 'Waiting Approval'],
    ['waiting_user', 'Waiting User'],
    ['resolved', 'Resolved'],
    ['closed', 'Closed'],
  ],
  priority: [
    ['low', 'Low'],
    ['medium', 'Medium'],
    ['high', 'High'],
    ['critical', 'Critical'],
  ],
  category: [
    ['cloud', 'Cloud'],
    ['cybersecurity', 'Cybersecurity'],
    ['identity_access', 'Identity and Access'],
    ['devops', 'DevOps'],
    ['internship_hr', 'Internship / HR'],
    ['general_it', 'General IT'],
  ],
  risk: [
    ['standard', 'Standard'],
    ['high', 'High Risk'],
  ],
};

function FilterSelect({ label, name, onChange, value }) {
  const values = options[name];

  return (
    <label className="ticket-filter-select">
      <span>{label}</span>
      <select name={name} value={value} onChange={onChange}>
        <option value="">All {label.toLowerCase()}</option>
        {values.map((option) => {
          const [optionValue, optionLabel] = Array.isArray(option)
            ? option
            : [option, option];
          return (
            <option key={optionValue} value={optionValue}>
              {optionLabel}
            </option>
          );
        })}
      </select>
    </label>
  );
}

export default function TicketFilters({ filters, onChange, onReset }) {
  const updateFilter = (event) => {
    onChange(event.target.name, event.target.value);
  };

  return (
    <section className="ticket-filters" aria-label="Ticket queue filters">
      <div className="ticket-filters__search">
        <span>Search</span>
        <SearchInput
          name="search"
          placeholder="Search by subject or requester"
          value={filters.search}
          onChange={updateFilter}
        />
      </div>
      <div className="ticket-filters__selects">
        <FilterSelect label="Source" name="source" value={filters.source} onChange={updateFilter} />
        <FilterSelect label="Status" name="status" value={filters.status} onChange={updateFilter} />
        <FilterSelect label="Priority" name="priority" value={filters.priority} onChange={updateFilter} />
        <FilterSelect label="Category" name="category" value={filters.category} onChange={updateFilter} />
        <FilterSelect label="Risk" name="risk" value={filters.risk} onChange={updateFilter} />
        <Button variant="outline" onClick={onReset}>
          Reset filters
        </Button>
      </div>
    </section>
  );
}
