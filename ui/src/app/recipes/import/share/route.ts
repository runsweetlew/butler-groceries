import { NextRequest, NextResponse } from 'next/server';

/**
 * Handle POST from Web Share Target API.
 * 
 * Android sends shared content as multipart/form-data POST.
 * We extract the URL/text/title and redirect to the share page with query params.
 * For shared photos, we store them temporarily and pass a reference.
 */
export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    
    const title = formData.get('title')?.toString() || '';
    const text = formData.get('text')?.toString() || '';
    const url = formData.get('url')?.toString() || '';
    
    // Check for shared photos
    const photos = formData.getAll('photos');
    
    if (photos.length > 0 && photos[0] instanceof File) {
      // Photo shared — forward to the photo import API directly
      const file = photos[0] as File;
      const apiFormData = new FormData();
      apiFormData.append('file', file);
      apiFormData.append('user_id', '1'); // Default to Lewis for share imports
      
      const apiUrl = process.env.API_INTERNAL_URL || 'http://butlergroceries-api:8080';
      const response = await fetch(`${apiUrl}/api/recipes/import/photo`, {
        method: 'POST',
        body: apiFormData,
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        return NextResponse.redirect(
          new URL(`/recipes/${result.recipe_id}`, request.url),
          303
        );
      } else {
        // Redirect to import page with error
        const params = new URLSearchParams({ error: result.error || 'Photo import failed' });
        return NextResponse.redirect(
          new URL(`/recipes/import?${params}`, request.url),
          303
        );
      }
    }

    // URL/text shared — redirect to shared page with params
    const params = new URLSearchParams();
    if (url) params.set('url', url);
    if (text) params.set('text', text);
    if (title) params.set('title', title);
    
    return NextResponse.redirect(
      new URL(`/recipes/import/shared?${params}`, request.url),
      303
    );
  } catch (error) {
    console.error('Share target error:', error);
    return NextResponse.redirect(
      new URL('/recipes/import', request.url),
      303
    );
  }
}
