/**
 * Downloads data as a CSV file
 * @param filename - The name of the file (without extension)
 * @param rows - Array of objects or arrays to convert to CSV
 * @param headers - Optional array of header names
 */
export function downloadAsCsv(
  filename: string,
  rows: (Record<string, any> | any[])[],
  headers?: string[]
): void {
  if (rows.length === 0) {
    console.warn('No data to export');
    return;
  }

  // Determine if rows are objects or arrays
  const isObjectRows = typeof rows[0] === 'object' && !Array.isArray(rows[0]);
  
  let csvContent = '';
  
  if (isObjectRows) {
    // Handle object rows
    const objectRows = rows as Record<string, any>[];
    const allKeys = new Set<string>();
    
    // Collect all possible keys
    objectRows.forEach(row => {
      Object.keys(row).forEach(key => allKeys.add(key));
    });
    
    const keys = headers || Array.from(allKeys);
    
    // Add headers
    csvContent += keys.map(key => `"${key}"`).join(',') + '\n';
    
    // Add data rows
    objectRows.forEach(row => {
      const values = keys.map(key => {
        const value = row[key];
        if (value === null || value === undefined) return '';
        if (typeof value === 'string' && value.includes(',')) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return `"${value}"`;
      });
      csvContent += values.join(',') + '\n';
    });
  } else {
    // Handle array rows
    const arrayRows = rows as any[][];
    
    if (headers) {
      csvContent += headers.map(header => `"${header}"`).join(',') + '\n';
    }
    
    arrayRows.forEach(row => {
      const values = row.map(value => {
        if (value === null || value === undefined) return '';
        if (typeof value === 'string' && value.includes(',')) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return `"${value}"`;
      });
      csvContent += values.join(',') + '\n';
    });
  }

  // Create and trigger download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
