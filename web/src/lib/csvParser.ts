import Papa from 'papaparse';

export interface CSVParsingResult {
  data: string[][];
  errors: Papa.ParseError[];
  meta: Papa.ParseMeta;
}

/**
 * Standardize CSV headers to handle case and space variations
 */
export function standardizeHeaders(headers: string[]): string[] {
  const headerMap: Record<string, string> = {
    // Account ID variations
    'acct id': 'acct_id',
    'acct_id': 'acct_id',
    'account id': 'acct_id',
    'account_id': 'acct_id',
    'acctid': 'acct_id',
    'accountid': 'acct_id',
    
    // Conversions variations
    'conversions': 'conversions',
    'conversion': 'conversions',
    'conv': 'conversions',
    'converted': 'conversions',
    
    // Clicks variations
    'clicks': 'clicks',
    'click': 'clicks',
    'unique_clicks': 'clicks',
    'unique clicks': 'clicks',
    
    // Conservative click estimate variations
    'conservative_click_estimate': 'conservative_click_estimate',
    'conservative click estimate': 'conservative_click_estimate',
    'conservative clicks': 'conservative_click_estimate',
    'conservative_clicks': 'conservative_click_estimate',
    'click_estimate': 'conservative_click_estimate',
    'click estimate': 'conservative_click_estimate',
    
    // Creator fields
    'name': 'name',
    'creator_name': 'name',
    'creator name': 'name',
    'owner_email': 'owner_email',
    'owner email': 'owner_email',
    'email': 'owner_email',
    'topic': 'topic',
    'category': 'topic',
    'niche': 'topic'
  };
  
  return headers.map(header => {
    const normalized = header.toLowerCase().trim();
    return headerMap[normalized] || header;
  });
}

/**
 * Parse CSV content using Papa Parse with proper handling of:
 * - Commas within quoted fields
 * - Escaped quotes
 * - Different line endings
 * - Various delimiters
 * - Malformed rows
 */
export function parseCSV(csvContent: string): CSVParsingResult {
  console.log('Raw CSV content length:', csvContent.length);
  console.log('First 200 chars:', csvContent.substring(0, 200));
  
  const result = Papa.parse<string[]>(csvContent, {
    // Skip empty lines
    skipEmptyLines: true,
    // Detect delimiter automatically
    delimiter: '',
    // Proper quote handling
    quoteChar: '"',
    // Escape character
    escapeChar: '"',
    // Transform values to trim whitespace
    transform: (value: string) => value?.trim() || ''
  });

  console.log('Papa Parse result:', result);
  console.log('Data length:', result.data?.length);
  console.log('First few rows:', result.data?.slice(0, 3));

  // Standardize headers if we have data
  if (result.data && result.data.length > 0) {
    const headers = result.data[0];
    const standardizedHeaders = standardizeHeaders(headers);
    console.log('Original headers:', headers);
    console.log('Standardized headers:', standardizedHeaders);
    
    // Replace the first row with standardized headers
    result.data[0] = standardizedHeaders;
  }

  return {
    data: result.data as string[][],
    errors: result.errors,
    meta: result.meta
  };
}

/**
 * Parse CSV file asynchronously with progress callback
 */
export function parseCSVFile(
  file: File, 
  onProgress?: (progress: number) => void
): Promise<CSVParsingResult> {
  console.log('Parsing file:', file.name, 'Size:', file.size, 'Type:', file.type);
  
  return new Promise((resolve, reject) => {
    // First try with auto-detection
    Papa.parse<string[]>(file, {
      skipEmptyLines: true,
      delimiter: '', // Auto-detect
      quoteChar: '"',
      escapeChar: '"',
      transform: (value: string) => value?.trim() || '',
      complete: (result) => {
        console.log('File parse complete (auto-detect):', result);
        console.log('Data length:', result.data?.length);
        console.log('First few rows:', result.data?.slice(0, 3));
        
        // If we got empty data, try with common delimiters
        if (!result.data || result.data.length === 0 || (result.data.length === 1 && result.data[0].length === 1 && !result.data[0][0])) {
          console.log('Auto-detect failed, trying common delimiters...');
          
          // Try comma first
          Papa.parse<string[]>(file, {
            skipEmptyLines: true,
            delimiter: ',',
            quoteChar: '"',
            escapeChar: '"',
            transform: (value: string) => value?.trim() || '',
            complete: (commaResult) => {
              console.log('Comma parse result:', commaResult);
              if (commaResult.data && commaResult.data.length > 0) {
                resolve({
                  data: commaResult.data as string[][],
                  errors: commaResult.errors,
                  meta: commaResult.meta
                });
                return;
              }
              
              // Try semicolon
              Papa.parse<string[]>(file, {
                skipEmptyLines: true,
                delimiter: ';',
                quoteChar: '"',
                escapeChar: '"',
                transform: (value: string) => value?.trim() || '',
                complete: (semicolonResult) => {
                  console.log('Semicolon parse result:', semicolonResult);
                  resolve({
                    data: semicolonResult.data as string[][],
                    errors: semicolonResult.errors,
                    meta: semicolonResult.meta
                  });
                },
                error: (error: any) => {
                  console.error('Semicolon parse error:', error);
                  reject(error);
                }
              });
            },
            error: (error: any) => {
              console.error('Comma parse error:', error);
              reject(error);
            }
          });
        } else {
          resolve({
            data: result.data as string[][],
            errors: result.errors,
            meta: result.meta
          });
        }
      },
      error: (error: any) => {
        console.error('File parse error:', error);
        reject(error);
      },
      step: (result) => {
        if (onProgress) {
          // Use a simple progress calculation
          const progress = Math.min(100, Math.max(0, (result.meta.cursor || 0) / (file.size || 1) * 100));
          onProgress(progress);
        }
      }
    });
  });
}

/**
 * Validate CSV structure and return helpful error messages
 */
export function validateCSVStructure(
  data: string[][], 
  requiredColumns: string[]
): { isValid: boolean; errors: string[]; columnMapping?: { [key: string]: string } } {
  const errors: string[] = [];
  
  if (data.length === 0) {
    errors.push('CSV file is empty');
    return { isValid: false, errors };
  }
  
  const headers = data[0];
  if (!headers || headers.length === 0) {
    errors.push('CSV file has no headers');
    return { isValid: false, errors };
  }
  
  // Check for required columns (case-insensitive and flexible matching)
  const headerMap = new Map(headers.map(h => [h.toLowerCase().trim(), h]));
  
  // Create flexible column mapping for common variations
  const columnVariations: { [key: string]: string[] } = {
    'name': ['name', 'creator name', 'creator_name', 'full name', 'full_name'],
    'acct_id': ['acct_id', 'acct id', 'account_id', 'account id', 'id', 'creator_id', 'creator id'],
    'owner_email': ['owner_email', 'owner email', 'email', 'creator_email', 'creator email', 'contact_email', 'contact email'],
    'topic': ['topic', 'category', 'niche', 'subject', 'theme']
  };
  
  const missingColumns: string[] = [];
  const foundColumns: { [key: string]: string } = {};
  
  for (const requiredCol of requiredColumns) {
    let found = false;
    const variations = columnVariations[requiredCol] || [requiredCol];
    
    for (const variation of variations) {
      if (headerMap.has(variation.toLowerCase())) {
        foundColumns[requiredCol] = headerMap.get(variation.toLowerCase())!;
        found = true;
        break;
      }
    }
    
    if (!found) {
      missingColumns.push(requiredCol);
    }
  }
  
  if (missingColumns.length > 0) {
    errors.push(`Missing required columns: ${missingColumns.join(', ')}`);
    errors.push(`Found columns: ${headers.join(', ')}`);
    errors.push(`Required columns: ${requiredColumns.join(', ')}`);
  }
  
  // Check for empty rows
  const emptyRows = data.slice(1).map((row, index) => 
    row.every(cell => !cell || cell.trim() === '') ? index + 2 : null
  ).filter(Boolean);
  
  if (emptyRows.length > 0) {
    errors.push(`Empty rows found at lines: ${emptyRows.join(', ')}`);
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    columnMapping: errors.length === 0 ? foundColumns : undefined
  };
}

/**
 * Get preview of CSV data (first N rows)
 */
export function getCSVPreview(data: string[][], maxRows: number = 5): string[][] {
  return data.slice(0, maxRows + 1); // +1 for header
}

/**
 * Format CSV parsing errors for display
 */
export function formatCSVErrors(errors: Papa.ParseError[]): string[] {
  return errors.map(error => {
    if (error.type === 'Delimiter') {
      return `Line ${error.row}: Could not determine delimiter`;
    } else if (error.type === 'Quotes') {
      return `Line ${error.row}: Mismatched quotes`;
    } else if (error.type === 'FieldMismatch') {
      return `Line ${error.row}: Field count mismatch - ${error.message}`;
    } else {
      return `Line ${error.row}: ${error.message}`;
    }
  });
}

/**
 * Debug function to help troubleshoot CSV issues
 */
export function debugCSVStructure(data: string[][]): string[] {
  const debug: string[] = [];
  
  if (data.length === 0) {
    debug.push('CSV is completely empty');
    return debug;
  }
  
  debug.push(`CSV has ${data.length} rows`);
  debug.push(`Headers: ${data[0]?.join(' | ') || 'None'}`);
  debug.push(`First data row: ${data[1]?.join(' | ') || 'None'}`);
  
  if (data.length > 2) {
    debug.push(`Sample of columns found:`);
    data[0]?.forEach((header, index) => {
      debug.push(`  Column ${index + 1}: "${header}" (length: ${header.length})`);
    });
  }
  
  return debug;
}
